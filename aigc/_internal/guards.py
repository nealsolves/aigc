"""
Guard evaluation engine for conditional policy expansion.

Guards use when/then rules to expand the effective policy based on
runtime context. Guard effects are additive and processed in order.

Supports AST-based guard expressions with boolean operators (and, or, not),
comparison operators (==, !=, <, >, <=, >=), and the 'in' operator.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping

from aigc._internal.conditions import resolve_conditions
from aigc._internal.errors import GuardEvaluationError


# ---------------------------------------------------------------------------
# AST node types for guard condition expressions
# ---------------------------------------------------------------------------

class _ASTNode:
    """Base class for AST nodes."""
    pass


class _BoolLookup(_ASTNode):
    """Lookup a boolean condition by name."""
    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name


class _NotExpr(_ASTNode):
    """Logical NOT."""
    __slots__ = ("operand",)

    def __init__(self, operand: _ASTNode):
        self.operand = operand


class _AndExpr(_ASTNode):
    """Logical AND."""
    __slots__ = ("left", "right")

    def __init__(self, left: _ASTNode, right: _ASTNode):
        self.left = left
        self.right = right


class _OrExpr(_ASTNode):
    """Logical OR."""
    __slots__ = ("left", "right")

    def __init__(self, left: _ASTNode, right: _ASTNode):
        self.left = left
        self.right = right


class _CompareExpr(_ASTNode):
    """Comparison expression (==, !=, <, >, <=, >=)."""
    __slots__ = ("left", "op", "right")

    def __init__(self, left: str, op: str, right: str):
        self.left = left
        self.op = op
        self.right = right


class _InExpr(_ASTNode):
    """Membership test: value in field."""
    __slots__ = ("value", "field")

    def __init__(self, value: str, field: str):
        self.value = value
        self.field = field


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

# Token pattern: keywords, comparison ops, quoted strings, identifiers
_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (and|or|not|in)(?=\s|$)    # keywords (must be followed by space/end)
      | ([!=<>]=|[<>])              # comparison operators
      | "([^"]*)"                   # double-quoted string
      | '([^']*)'                   # single-quoted string
      | (\(|\))                     # parentheses
      | ([A-Za-z_][A-Za-z0-9_.]*)  # identifiers (including dotted paths)
      | (-?\d+(?:\.\d+)?)          # numbers
    )\s*
    """,
    re.VERBOSE,
)

_KEYWORDS = frozenset({"and", "or", "not", "in"})


def _tokenize(expr: str) -> list[tuple[str, str]]:
    """
    Tokenize a guard expression into (type, value) pairs.

    Token types: KEYWORD, OP, STRING, IDENT, PAREN, NUMBER
    """
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        # Skip whitespace
        while pos < len(expr) and expr[pos].isspace():
            pos += 1
        if pos >= len(expr):
            break

        m = _TOKEN_RE.match(expr, pos)
        if not m:
            raise GuardEvaluationError(
                f"Unexpected character in guard expression at position {pos}: "
                f"'{expr[pos]}'",
                details={"expression": expr, "position": pos},
            )

        if m.group(1):  # keyword
            tokens.append(("KEYWORD", m.group(1)))
        elif m.group(2):  # comparison operator
            tokens.append(("OP", m.group(2)))
        elif m.group(3) is not None:  # double-quoted string
            tokens.append(("STRING", m.group(3)))
        elif m.group(4) is not None:  # single-quoted string
            tokens.append(("STRING", m.group(4)))
        elif m.group(5):  # parentheses
            tokens.append(("PAREN", m.group(5)))
        elif m.group(6):  # identifier
            tokens.append(("IDENT", m.group(6)))
        elif m.group(7) is not None:  # number
            tokens.append(("NUMBER", m.group(7)))
        else:
            raise GuardEvaluationError(
                f"Unexpected token in guard expression: '{expr[pos:]}'",
                details={"expression": expr, "position": pos},
            )

        pos = m.end()

    return tokens


# ---------------------------------------------------------------------------
# Recursive descent parser
# ---------------------------------------------------------------------------

class _Parser:
    """
    Recursive descent parser for guard condition expressions.

    Grammar:
        expr     -> or_expr
        or_expr  -> and_expr ('or' and_expr)*
        and_expr -> not_expr ('and' not_expr)*
        not_expr -> 'not' not_expr | primary
        primary  -> '(' expr ')' | comparison | in_expr | bool_lookup
        comparison -> IDENT OP (IDENT | STRING | NUMBER)
        in_expr  -> (STRING | IDENT) 'in' IDENT
        bool_lookup -> IDENT
    """

    def __init__(self, tokens: list[tuple[str, str]], expr: str):
        self.tokens = tokens
        self.pos = 0
        self.expr = expr

    def _peek(self) -> tuple[str, str] | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self) -> tuple[str, str]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, ttype: str, tvalue: str | None = None) -> tuple[str, str]:
        tok = self._peek()
        if tok is None:
            raise GuardEvaluationError(
                f"Unexpected end of guard expression: '{self.expr}'",
                details={"expression": self.expr},
            )
        if tok[0] != ttype or (tvalue is not None and tok[1] != tvalue):
            raise GuardEvaluationError(
                f"Expected {ttype}({tvalue}) but got {tok[0]}({tok[1]}) "
                f"in guard expression: '{self.expr}'",
                details={"expression": self.expr},
            )
        return self._advance()

    def parse(self) -> _ASTNode:
        node = self._parse_or()
        if self.pos < len(self.tokens):
            remaining = self.tokens[self.pos:]
            raise GuardEvaluationError(
                f"Unexpected tokens after expression: "
                f"{[t[1] for t in remaining]} in '{self.expr}'",
                details={"expression": self.expr},
            )
        return node

    def _parse_or(self) -> _ASTNode:
        left = self._parse_and()
        while (tok := self._peek()) and tok == ("KEYWORD", "or"):
            self._advance()
            right = self._parse_and()
            left = _OrExpr(left, right)
        return left

    def _parse_and(self) -> _ASTNode:
        left = self._parse_not()
        while (tok := self._peek()) and tok == ("KEYWORD", "and"):
            self._advance()
            right = self._parse_not()
            left = _AndExpr(left, right)
        return left

    def _parse_not(self) -> _ASTNode:
        tok = self._peek()
        if tok and tok == ("KEYWORD", "not"):
            self._advance()
            operand = self._parse_not()
            return _NotExpr(operand)
        return self._parse_primary()

    def _parse_primary(self) -> _ASTNode:
        tok = self._peek()
        if tok is None:
            raise GuardEvaluationError(
                f"Unexpected end of guard expression: '{self.expr}'",
                details={"expression": self.expr},
            )

        # Parenthesized expression
        if tok == ("PAREN", "("):
            self._advance()
            node = self._parse_or()
            self._expect("PAREN", ")")
            return node

        # String literal followed by 'in' -> in-expression
        if tok[0] == "STRING":
            next_pos = self.pos + 1
            if (next_pos < len(self.tokens)
                    and self.tokens[next_pos] == ("KEYWORD", "in")):
                val_tok = self._advance()
                self._advance()  # consume 'in'
                field_tok = self._expect("IDENT")
                return _InExpr(val_tok[1], field_tok[1])
            # Standalone string not supported
            raise GuardEvaluationError(
                f"Unexpected string literal in guard expression: '{self.expr}'",
                details={"expression": self.expr},
            )

        # Identifier: could be comparison, 'in' expression, or bool lookup
        if tok[0] == "IDENT":
            # Look ahead for comparison operator
            next_pos = self.pos + 1
            if next_pos < len(self.tokens):
                next_tok = self.tokens[next_pos]

                # Comparison: ident OP value
                if next_tok[0] == "OP":
                    ident_tok = self._advance()
                    op_tok = self._advance()
                    val_tok = self._peek()
                    if val_tok is None:
                        raise GuardEvaluationError(
                            f"Expected value after operator in: '{self.expr}'",
                            details={"expression": self.expr},
                        )
                    self._advance()
                    return _CompareExpr(
                        ident_tok[1], op_tok[1], val_tok[1]
                    )

                # ident 'in' ident -> in-expression
                if next_tok == ("KEYWORD", "in"):
                    val_tok = self._advance()
                    self._advance()  # consume 'in'
                    field_tok = self._expect("IDENT")
                    return _InExpr(val_tok[1], field_tok[1])

            # Simple boolean lookup
            ident_tok = self._advance()
            return _BoolLookup(ident_tok[1])

        raise GuardEvaluationError(
            f"Unexpected token '{tok[1]}' in guard expression: '{self.expr}'",
            details={"expression": self.expr},
        )


# ---------------------------------------------------------------------------
# Compilation: expression string -> AST
# ---------------------------------------------------------------------------

def compile_guard_expression(expr: str) -> _ASTNode:
    """
    Compile a guard condition expression string into an AST.

    Supported syntax:
    - Boolean lookup: ``is_enterprise``
    - Equality: ``role == verifier`` or ``role == "verifier"``
    - Comparison: ``count > 5``, ``score <= 0.8``
    - Not equal: ``role != admin``
    - Logical AND: ``is_enterprise and audit_enabled``
    - Logical OR: ``is_enterprise or is_government``
    - Logical NOT: ``not is_internal``
    - Parentheses: ``(is_enterprise or is_government) and audit_enabled``
    - Membership: ``"search" in allowed_tools`` or ``role in admin_roles``

    :param expr: Guard condition expression string
    :return: Compiled AST node
    :raises GuardEvaluationError: On syntax errors
    """
    expr = expr.strip()
    if not expr:
        raise GuardEvaluationError(
            "Empty guard condition expression",
            details={"expression": expr},
        )
    tokens = _tokenize(expr)
    parser = _Parser(tokens, expr)
    return parser.parse()


# ---------------------------------------------------------------------------
# Evaluation: AST + context -> bool
# ---------------------------------------------------------------------------

def _resolve_value(
    name: str,
    resolved_conditions: Mapping[str, bool],
    invocation: Mapping[str, Any],
) -> Any:
    """Resolve an identifier to a value from conditions or invocation."""
    if name == "role":
        return invocation.get("role")
    if name in resolved_conditions:
        return resolved_conditions[name]
    # Check invocation context
    ctx = invocation.get("context", {})
    if name in ctx:
        return ctx[name]
    return None


def _coerce_value(raw: str) -> Any:
    """Coerce a string token value to an appropriate Python type."""
    # Try integer
    try:
        return int(raw)
    except (ValueError, TypeError):
        pass
    # Try float
    try:
        return float(raw)
    except (ValueError, TypeError):
        pass
    # Boolean literals
    if raw == "true":
        return True
    if raw == "false":
        return False
    # String
    return raw


def evaluate_ast(
    node: _ASTNode,
    resolved_conditions: Mapping[str, bool],
    invocation: Mapping[str, Any],
) -> bool:
    """
    Evaluate a compiled guard expression AST.

    :param node: Compiled AST node
    :param resolved_conditions: Pre-resolved named conditions
    :param invocation: Full invocation dict
    :return: Boolean result
    :raises GuardEvaluationError: On evaluation errors
    """
    if isinstance(node, _BoolLookup):
        if node.name in resolved_conditions:
            return bool(resolved_conditions[node.name])
        raise GuardEvaluationError(
            f"Unknown condition in guard expression: {node.name}",
            details={
                "expression": node.name,
                "available_conditions": list(resolved_conditions.keys()),
            },
        )

    if isinstance(node, _NotExpr):
        return not evaluate_ast(node.operand, resolved_conditions, invocation)

    if isinstance(node, _AndExpr):
        return (evaluate_ast(node.left, resolved_conditions, invocation)
                and evaluate_ast(node.right, resolved_conditions, invocation))

    if isinstance(node, _OrExpr):
        return (evaluate_ast(node.left, resolved_conditions, invocation)
                or evaluate_ast(node.right, resolved_conditions, invocation))

    if isinstance(node, _CompareExpr):
        left_val = _resolve_value(
            node.left, resolved_conditions, invocation
        )
        right_val = _coerce_value(node.right)

        if node.op == "==":
            return left_val == right_val
        if node.op == "!=":
            return left_val != right_val
        # Numeric comparisons
        try:
            left_num = float(left_val) if left_val is not None else 0.0
            right_num = float(right_val)
        except (ValueError, TypeError):
            raise GuardEvaluationError(
                f"Cannot compare non-numeric values: "
                f"{left_val!r} {node.op} {right_val!r}",
                details={
                    "left": node.left,
                    "op": node.op,
                    "right": node.right,
                },
            )
        if node.op == "<":
            return left_num < right_num
        if node.op == ">":
            return left_num > right_num
        if node.op == "<=":
            return left_num <= right_num
        if node.op == ">=":
            return left_num >= right_num
        raise GuardEvaluationError(
            f"Unknown comparison operator: {node.op}",
            details={"op": node.op},
        )

    if isinstance(node, _InExpr):
        container = _resolve_value(
            node.field, resolved_conditions, invocation
        )
        if container is None:
            return False
        if isinstance(container, (list, tuple, set, frozenset)):
            return _coerce_value(node.value) in container
        if isinstance(container, str):
            return node.value in container
        return False

    raise GuardEvaluationError(
        f"Unknown AST node type: {type(node).__name__}",
        details={"node_type": type(node).__name__},
    )


# ---------------------------------------------------------------------------
# Public API (backward-compatible)
# ---------------------------------------------------------------------------

def _merge_policy_blocks(base: dict[str, Any], overlay: Mapping[str, Any]) -> None:
    """
    Merge overlay into base dict (in-place, additive semantics).

    Rules:
    - Arrays: append overlay items to base array
    - Dicts: recursive merge
    - Scalars: overlay replaces base

    :param base: Base dict to merge into (modified in-place)
    :param overlay: Overlay dict to merge from
    """
    for key, value in overlay.items():
        if key not in base:
            base[key] = copy.deepcopy(value)
        elif isinstance(base[key], list) and isinstance(value, list):
            base[key].extend(copy.deepcopy(value))
        elif isinstance(base[key], dict) and isinstance(value, dict):
            _merge_policy_blocks(base[key], value)
        else:
            # Scalar replacement
            base[key] = copy.deepcopy(value)


def _evaluate_condition_expression(
    expr: str,
    resolved_conditions: Mapping[str, bool],
    invocation: Mapping[str, Any],
) -> bool:
    """
    Evaluate a guard condition expression using the AST-based engine.

    Supports:
    - Boolean lookup: "is_enterprise"
    - Equality: "role == verifier"
    - Comparison: "count > 5"
    - Logical: "is_enterprise and audit_enabled"
    - Logical: "is_enterprise or is_government"
    - Negation: "not is_internal"
    - Parentheses: "(a or b) and c"
    - Membership: '"search" in allowed_tools'

    :param expr: Condition expression string
    :param resolved_conditions: Pre-resolved named conditions
    :param invocation: Full invocation dict (for role checks)
    :return: Boolean result
    :raises GuardEvaluationError: On unknown condition or syntax error
    """
    ast = compile_guard_expression(expr)
    return evaluate_ast(ast, resolved_conditions, invocation)


def evaluate_guards(
    policy: Mapping[str, Any],
    context: Mapping[str, Any],
    invocation: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, bool]]:
    """
    Evaluate guards and produce effective policy.

    :param policy: Original policy dict
    :param context: Invocation context
    :param invocation: Full invocation (for role checks in guard conditions)
    :return: Tuple of (effective_policy, guards_evaluated, conditions_resolved)

    guards_evaluated format:
        [{"condition": "is_enterprise", "matched": True}, ...]

    conditions_resolved format:
        {"is_enterprise": True, "audit_enabled": False}
    """
    guards = policy.get("guards", [])

    # Resolve conditions first (even if no guards, for audit metadata)
    resolved_conditions = resolve_conditions(policy, context)

    if not guards:
        return dict(policy), [], resolved_conditions

    # Evaluate all guard conditions first (no copies yet)
    guards_evaluated: list[dict[str, Any]] = []
    matching_effects: list[Mapping[str, Any]] = []

    for guard in guards:
        when_clause = guard.get("when", {})
        condition_expr = when_clause.get("condition", "")

        matched = _evaluate_condition_expression(
            condition_expr, resolved_conditions, invocation
        )

        guards_evaluated.append(
            {
                "condition": condition_expr,
                "matched": matched,
            }
        )

        if matched:
            then_clause = guard.get("then", {})
            if then_clause:
                matching_effects.append(then_clause)

    # Single deep copy, then apply all matching effects in order
    effective_policy = copy.deepcopy(dict(policy))
    for effect in matching_effects:
        _merge_policy_blocks(effective_policy, effect)

    return effective_policy, guards_evaluated, resolved_conditions
