from __future__ import annotations

from dataclasses import dataclass, replace
from html import escape
from pathlib import Path
from textwrap import dedent


SVG_NS = "http://www.w3.org/2000/svg"
WIDTH = 1600
HOST_BAND = (60, 72, 1480, 138)


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    page_border: str
    title: str
    subtitle: str
    section: str
    text: str
    subtext: str
    note: str
    small: str
    neutral_fill: str
    neutral_border: str
    policy_fill: str
    policy_border: str
    workflow_fill: str
    workflow_border: str
    kernel_fill: str
    kernel_border: str
    evidence_fill: str
    evidence_border: str
    ops_fill: str
    ops_border: str
    adapter_fill: str
    adapter_border: str
    note_fill: str
    note_border: str
    connector: str
    connector_muted: str


LIGHT = Theme(
    name="light",
    background="#f5f7fb",
    page_border="#d6dde8",
    title="#0b5cc5",
    subtitle="#5d6a7a",
    section="#5b6575",
    text="#152235",
    subtext="#5b6878",
    note="#364252",
    small="#758296",
    neutral_fill="#ffffff",
    neutral_border="#c6cfda",
    policy_fill="#eef3f8",
    policy_border="#b9c6d8",
    workflow_fill="#edf5ff",
    workflow_border="#2f6feb",
    kernel_fill="#f4efff",
    kernel_border="#6f5ef5",
    evidence_fill="#edf8ef",
    evidence_border="#3aa35b",
    ops_fill="#f2f5f8",
    ops_border="#c0c9d6",
    adapter_fill="#f6f4ff",
    adapter_border="#7a71ea",
    note_fill="#ffffff",
    note_border="#d4dce7",
    connector="#5c7394",
    connector_muted="#97a6b8",
)

DARK = Theme(
    name="dark",
    background="#0b1118",
    page_border="#2b3443",
    title="#8ab8ff",
    subtitle="#95a4ba",
    section="#adbace",
    text="#eef4ff",
    subtext="#b8c4d8",
    note="#d9e3f1",
    small="#8190a7",
    neutral_fill="#131b24",
    neutral_border="#354152",
    policy_fill="#141d29",
    policy_border="#47576c",
    workflow_fill="#11253e",
    workflow_border="#68a3ff",
    kernel_fill="#22163a",
    kernel_border="#9a82ff",
    evidence_fill="#13281c",
    evidence_border="#57c372",
    ops_fill="#151d28",
    ops_border="#3b4758",
    adapter_fill="#111826",
    adapter_border="#7a8db3",
    note_fill="#101721",
    note_border="#303b4b",
    connector="#8ea7c8",
    connector_muted="#5b6b80",
)


def xml(text: str) -> str:
    return escape(text, quote=False)


def css(theme: Theme, height: int) -> str:
    return dedent(
        f"""
        <style>
          svg {{
            font-family: 'IBM Plex Sans', 'Avenir Next', 'Segoe UI', sans-serif;
          }}
          .mono {{
            font-family: 'IBM Plex Mono', 'SFMono-Regular', 'Menlo', monospace;
          }}
          .page-title {{
            fill: {theme.title};
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0.04em;
          }}
          .page-subtitle {{
            fill: {theme.subtitle};
            font-size: 15px;
          }}
          .section-tag {{
            fill: {theme.section};
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.16em;
          }}
          .panel-title {{
            fill: {theme.section};
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.14em;
          }}
          .box-title {{
            fill: {theme.text};
            font-size: 18px;
            font-weight: 600;
          }}
          .box-sub {{
            fill: {theme.subtext};
            font-size: 13px;
            font-weight: 500;
          }}
          .body {{
            fill: {theme.note};
            font-size: 14px;
            font-weight: 500;
          }}
          .body-plus {{
            fill: {theme.note};
            font-size: 15px;
            font-weight: 500;
          }}
          .small {{
            fill: {theme.small};
            font-size: 12px;
          }}
          .small-plus {{
            fill: {theme.small};
            font-size: 13px;
          }}
          .footer-note {{
            fill: {theme.note};
            font-size: 14px;
            font-weight: 500;
          }}
          .footer-note-lg {{
            fill: {theme.note};
            font-size: 15px;
            font-weight: 500;
          }}
          .footer-small {{
            fill: {theme.small};
            font-size: 12px;
          }}
          .footer-small-lg {{
            fill: {theme.small};
            font-size: 13px;
          }}
          .frame {{
            fill: none;
            stroke: {theme.page_border};
            stroke-width: 1.4;
          }}
          .band {{
            fill: {theme.neutral_fill};
            stroke: {theme.page_border};
            stroke-width: 1.4;
          }}
          .host-box {{
            fill: {theme.neutral_fill};
            stroke: {theme.neutral_border};
            stroke-width: 1.4;
          }}
          .policy-panel {{
            fill: {theme.policy_fill};
            stroke: {theme.policy_border};
            stroke-width: 1.5;
          }}
          .workflow-panel {{
            fill: {theme.workflow_fill};
            stroke: {theme.workflow_border};
            stroke-width: 1.7;
          }}
          .kernel-panel {{
            fill: {theme.kernel_fill};
            stroke: {theme.kernel_border};
            stroke-width: 1.7;
          }}
          .evidence-panel {{
            fill: {theme.evidence_fill};
            stroke: {theme.evidence_border};
            stroke-width: 1.6;
          }}
          .ops-panel {{
            fill: {theme.ops_fill};
            stroke: {theme.ops_border};
            stroke-width: 1.4;
          }}
          .adapter-panel {{
            fill: {theme.adapter_fill};
            stroke: {theme.adapter_border};
            stroke-width: 1.4;
            stroke-dasharray: 8 7;
          }}
          .note-box {{
            fill: {theme.note_fill};
            stroke: {theme.note_border};
            stroke-width: 1.2;
          }}
          .node-neutral {{
            fill: {theme.neutral_fill};
            stroke: {theme.neutral_border};
            stroke-width: 1.3;
          }}
          .node-policy {{
            fill: {theme.neutral_fill};
            stroke: {theme.policy_border};
            stroke-width: 1.3;
          }}
          .node-workflow {{
            fill: {theme.neutral_fill};
            stroke: {theme.workflow_border};
            stroke-width: 1.35;
          }}
          .node-kernel {{
            fill: {theme.neutral_fill};
            stroke: {theme.kernel_border};
            stroke-width: 1.35;
          }}
          .node-evidence {{
            fill: {theme.neutral_fill};
            stroke: {theme.evidence_border};
            stroke-width: 1.35;
          }}
          .node-ops {{
            fill: {theme.note_fill};
            stroke: {theme.ops_border};
            stroke-width: 1.25;
          }}
          .node-adapter {{
            fill: {theme.note_fill};
            stroke: {theme.adapter_border};
            stroke-width: 1.25;
            stroke-dasharray: 7 6;
          }}
          .connector {{
            fill: none;
            stroke: {theme.connector};
            stroke-width: 2.3;
            stroke-linecap: round;
            stroke-linejoin: round;
          }}
          .connector-muted {{
            fill: none;
            stroke: {theme.connector_muted};
            stroke-width: 2.0;
            stroke-linecap: round;
            stroke-linejoin: round;
            stroke-dasharray: 7 7;
          }}
          .connector-soft {{
            fill: none;
            stroke: {theme.connector};
            stroke-opacity: 0.68;
            stroke-width: 1.7;
            stroke-linecap: round;
            stroke-linejoin: round;
          }}
        </style>
        <marker id="arrow" viewBox="0 0 12 10" refX="10" refY="5" markerWidth="10" markerHeight="8" orient="auto">
          <path d="M0 0 L12 5 L0 10 z" fill="{theme.connector}" />
        </marker>
        <marker id="arrow-muted" viewBox="0 0 12 10" refX="10" refY="5" markerWidth="10" markerHeight="8" orient="auto">
          <path d="M0 0 L12 5 L0 10 z" fill="{theme.connector_muted}" />
        </marker>
        <marker id="arrow-soft" viewBox="0 0 12 10" refX="10" refY="5" markerWidth="10" markerHeight="8" orient="auto">
          <path d="M0 0 L12 5 L0 10 z" fill="{theme.connector}" fill-opacity="0.68" />
        </marker>
        """
    ).strip()


def header(theme: Theme, title: str, subtitle: str, height: int) -> str:
    return (
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 {WIDTH} {height}">'
        f"<defs>{css(theme, height)}</defs>"
        f'<rect width="{WIDTH}" height="{height}" fill="{theme.background}" rx="24" />'
        f'<rect x="36" y="36" width="{WIDTH - 72}" height="{height - 72}" class="frame" rx="24" />'
        f'<text class="page-title mono" x="60" y="44">{xml(title)}</text>'
        f'<text class="page-subtitle" x="60" y="68">{xml(subtitle)}</text>'
    )


def footer() -> str:
    return "</svg>"


def rect(x: int, y: int, w: int, h: int, cls: str, rx: int = 20) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" class="{cls}" />'


def section_text(x: int, y: int, text: str) -> str:
    return f'<text class="section-tag mono" x="{x}" y="{y}">{xml(text)}</text>'


def panel_text(x: int, y: int, text: str) -> str:
    return f'<text class="panel-title mono" x="{x}" y="{y}">{xml(text)}</text>'


def lines_text(
    x: int,
    y_center: float,
    lines: list[tuple[str, str]],
    anchor: str = "middle",
    line_gap: int = 6,
) -> str:
    heights: dict[str, int] = {
        "box-title": 22,
        "box-sub": 17,
        "body": 18,
        "body-plus": 19,
        "small": 14,
        "small-plus": 15,
        "footer-note": 18,
        "footer-note-lg": 19,
        "footer-small": 14,
        "footer-small-lg": 15,
    }
    total = sum(heights[cls] for cls, _ in lines)
    total += line_gap * max(len(lines) - 1, 0)
    current = y_center - total / 2
    anchor_attr = f'text-anchor="{anchor}"'
    out: list[str] = []
    for cls, text in lines:
        line_height = heights[cls]
        cy = current + line_height / 2
        out.append(f'<text class="{cls}" x="{x}" y="{cy}" {anchor_attr}>{xml(text)}</text>')
        current += line_height + line_gap
    return "".join(out)


def node(
    x: int,
    y: int,
    w: int,
    h: int,
    cls: str,
    title_lines: list[str],
    subtitle_lines: list[str] | None = None,
    rx: int = 18,
) -> str:
    lines: list[tuple[str, str]] = [("box-title", text) for text in title_lines]
    if subtitle_lines:
        lines.extend(("box-sub", text) for text in subtitle_lines)
    return rect(x, y, w, h, cls, rx=rx) + lines_text(x + w // 2, y + h / 2, lines)


def note_node(
    x: int,
    y: int,
    w: int,
    h: int,
    title_lines: list[str],
    subtitle_lines: list[str] | None = None,
    cls: str = "note-box",
    rx: int = 18,
    body_cls: str = "body",
    small_cls: str = "small",
) -> str:
    lines: list[tuple[str, str]] = [(body_cls, text) for text in title_lines]
    if subtitle_lines:
        lines.extend((small_cls, text) for text in subtitle_lines)
    return rect(x, y, w, h, cls, rx=rx) + lines_text(x + w // 2, y + h / 2, lines)


def text_box(
    x: int,
    y: int,
    w: int,
    h: int,
    cls: str,
    body_lines: list[str],
    small_lines: list[str] | None = None,
    rx: int = 18,
    body_cls: str = "body",
    small_cls: str = "small",
) -> str:
    lines: list[tuple[str, str]] = [(body_cls, text) for text in body_lines]
    if small_lines:
        lines.extend((small_cls, text) for text in small_lines)
    return rect(x, y, w, h, cls, rx=rx) + lines_text(x + w // 2, y + h / 2, lines)


def path(d: str, muted: bool = False, soft: bool = False) -> str:
    if soft:
        cls = "connector-soft"
        marker = "arrow-soft"
    else:
        cls = "connector-muted" if muted else "connector"
        marker = "arrow-muted" if muted else "arrow"
    return f'<path class="{cls}" d="{d}" marker-end="url(#{marker})" />'


def render_beta(theme: Theme) -> str:
    if theme.name == "light":
        theme = replace(
            theme,
            page_border="#cad4e1",
            neutral_border="#bcc7d6",
            policy_border="#afbed4",
            subtitle="#536276",
            section="#586476",
            subtext="#4f6073",
            note="#2f3b4c",
            small="#6e7c91",
            note_border="#c7d2df",
            connector="#587296",
            connector_muted="#8ea1ba",
        )
    else:
        theme = replace(
            theme,
            page_border="#334153",
            neutral_border="#405064",
            subtitle="#a3b2c8",
            section="#b4c2d8",
            subtext="#c7d3e8",
            note="#e2ebf8",
            small="#95a6bd",
            note_border="#334152",
            connector="#93acce",
            connector_muted="#6a7c94",
        )

    height = 1240
    parts = [
        header(
            theme,
            "AIGC v0.9.0 BETA",
            "Source-only beta surface on local develop. The installable package remains v0.3.3.",
            height,
        ),
        rect(*HOST_BAND, "band", rx=24),
        section_text(84, 96, "HOST APPLICATION"),
    ]

    parts.extend(
        [
            node(92, 114, 302, 72, "host-box", ["App / Agent / Orchestrator"]),
            node(418, 114, 338, 72, "host-box", ["Provider / Tool /", "Transport Runtime"]),
            text_box(
                782,
                110,
                670,
                80,
                "note-box",
                ["Host owns execution, retries, credentials, and business state."],
                ["Provider and tool calls remain outside AIGC after authorization."],
            ),
        ]
    )

    main = (60, 238, 1480, 764)
    parts.extend(
        [
            rect(*main, "band", rx=24),
            section_text(84, 262, "AIGC SDK v0.9.0 BETA SURFACE"),
            rect(90, 286, 300, 480, "policy-panel", rx=22),
            panel_text(114, 314, "POLICY + LOADING"),
            rect(418, 286, 780, 258, "workflow-panel", rx=22),
            panel_text(444, 314, "WORKFLOW GOVERNANCE LAYER"),
            rect(418, 570, 780, 296, "kernel-panel", rx=22),
            panel_text(444, 590, "INVOCATION ENTRYPOINTS + DETERMINISTIC KERNEL"),
            rect(1222, 286, 290, 580, "evidence-panel", rx=22),
            panel_text(1246, 314, "EVIDENCE + SUPPORT"),
        ]
    )

    # Policy + loading
    parts.extend(
        [
            node(112, 336, 124, 78, "node-policy", ["Policy YAML"]),
            node(254, 336, 124, 78, "node-policy", ["PolicyCache"]),
            node(112, 432, 124, 90, "node-policy", ["FilePolicyLoader"], ["or PolicyLoaderBase"]),
            node(254, 432, 124, 90, "node-policy", ["JSON Schemas"]),
            note_node(
                110,
                558,
                268,
                126,
                ["Load, validate, cache, and", "compose policy contracts."],
                ["This surface remains SDK-owned", "and deterministic."],
            ),
        ]
    )

    # Workflow layer
    parts.extend(
        [
            node(448, 336, 168, 88, "node-workflow", ["AIGC.open_session()"]),
            node(642, 336, 174, 88, "node-workflow", ["GovernanceSession"]),
            node(
                842,
                336,
                188,
                88,
                "node-workflow",
                ["SessionPreCallResult"],
                ["workflow-bound split token"],
            ),
            node(1054, 336, 122, 88, "node-workflow", ["Workflow DSL"], ["sequence, budgets,", "approvals"]),
            note_node(
                448,
                454,
                374,
                72,
                ["Tracks steps, checkpoints, participants, and budgets."],
            ),
            node(
                842,
                446,
                334,
                94,
                "node-evidence",
                ["Workflow artifact"],
                ["COMPLETED | FAILED |", "CANCELED | INCOMPLETE"],
            ),
        ]
    )

    # Kernel
    parts.extend(
        [
            node(448, 620, 168, 88, "node-kernel", ["enforce_invocation()"]),
            node(642, 620, 168, 88, "node-kernel", ["AIGC.enforce()"]),
            node(842, 620, 188, 88, "node-kernel", ["split APIs"], ["pre_call / post_call"]),
            node(1048, 620, 128, 88, "node-kernel", ["ordered gates"], ["auth -> output -> risk"]),
            text_box(
                448,
                736,
                728,
                96,
                "node-kernel",
                [
                    "pre_authorization -> guards -> role -> preconditions -> tools -> post_authorization",
                    "pre_output -> schema -> postconditions -> post_output -> risk",
                ],
            ),
        ]
    )

    # Evidence/support
    parts.extend(
        [
            node(
                1246,
                336,
                242,
                88,
                "node-evidence",
                ["Invocation artifact"],
                ["PASS or FAIL per invocation attempt"],
            ),
            node(
                1246,
                466,
                242,
                96,
                "node-evidence",
                ["AuditSink + signing"],
                ["JSONL, callback, custom sink, optional signer"],
            ),
            node(
                1246,
                604,
                242,
                100,
                "node-ops",
                ["AuditLineage /", "compliance export --lineage"],
                ["stored-trail analysis"],
            ),
            note_node(
                1242,
                736,
                250,
                124,
                ["Workflow evidence stays separate", "from invocation artifacts."],
                ["Correlation is additive. It does not", "replace invocation evidence."],
                body_cls="body-plus",
                small_cls="small-plus",
            ),
        ]
    )

    # Bottom operator band
    parts.extend(
        [
            rect(60, 1028, 1480, 100, "ops-panel", rx=24),
            section_text(84, 1052, "BETA ADOPTION + OPERATOR SURFACES"),
            node(92, 1060, 238, 46, "node-ops", ["aigc workflow init"], rx=14),
            node(356, 1060, 238, 46, "node-ops", ["aigc workflow lint"], rx=14),
            node(620, 1060, 238, 46, "node-ops", ["aigc workflow doctor"], rx=14),
            text_box(
                888,
                1054,
                620,
                58,
                "note-box",
                ["Beta adopter flow + diagnosis around starter and workflow state."],
            ),
        ]
    )

    # Connectors
    parts.extend(
        [
            path("M243 186 V214 H532 V336", soft=True),
            path("M378 375 H418 V380 H448"),
            path("M378 477 H404 V664 H448"),
            path("M808 544 V570"),
            path("M936 424 V620"),
            path("M1176 493 H1220 V514 H1246"),
            path("M1176 664 H1214 V380 H1246"),
            path("M1367 424 V466"),
            path("M1367 562 V604"),
        ]
    )

    # Footer notes
    parts.extend(
        [
            lines_text(
                60,
                1160,
                [("footer-note-lg", "The host still performs provider and tool calls after AIGC authorizes a step or invocation.")],
                anchor="start",
            ),
            lines_text(
                60,
                1188,
                [("footer-note-lg", "The beta adds workflow evidence. It does not collapse AIGC into a hosted orchestrator.")],
                anchor="start",
            ),
            lines_text(
                60,
                1218,
                [
                    (
                        "footer-small-lg",
                        "Planned-only public items intentionally omitted: AgentIdentity, AgentCapabilityManifest,",
                    ),
                    ("footer-small-lg", "public ValidatorHook, BedrockTraceAdapter, A2AAdapter, workflow trace/export."),
                ],
                anchor="start",
            ),
        ]
    )
    parts.append(footer())
    return "".join(parts)


def render_full(theme: Theme) -> str:
    height = 1290
    parts = [
        header(
            theme,
            "AIGC v0.9.0 FULL",
            "Intended full solution design surface. AIGC remains an SDK, not a hosted runtime or orchestrator.",
            height,
        ),
        rect(*HOST_BAND, "band", rx=24),
        section_text(84, 96, "HOST APPLICATION"),
    ]

    parts.extend(
        [
            node(92, 116, 274, 68, "host-box", ["orchestration", "business logic"]),
            node(392, 116, 248, 68, "host-box", ["model calls", "tool execution"]),
            node(666, 116, 222, 68, "host-box", ["transport", "credentials"]),
            text_box(
                914,
                116,
                594,
                68,
                "note-box",
                ["Host-owned execution remains outside AIGC governance surfaces."],
                ["Adapters normalize host-visible evidence only; they do not replace core enforcement."],
            ),
        ]
    )

    parts.extend(
        [
            rect(60, 228, 1480, 112, "adapter-panel", rx=24),
            section_text(84, 252, "OPTIONAL ADAPTERS"),
            node(100, 264, 250, 56, "node-adapter", ["Bedrock adapter"], ["optional normalization"]),
            node(380, 264, 250, 56, "node-adapter", ["A2A adapter"], ["optional normalization"]),
            text_box(
                676,
                258,
                796,
                68,
                "note-box",
                ["Governance normalization inlet for host-supplied parsed trace, card, and task evidence."],
                ["Optional. Does not own HTTP clients, auth flows, retries, sockets, or remote sessions."],
            ),
        ]
    )

    parts.extend(
        [
            rect(60, 370, 1480, 854, "band", rx=24),
            section_text(84, 394, "AIGC SDK v0.9.0 FULL SURFACE"),
            rect(90, 416, 1038, 126, "policy-panel", rx=22),
            panel_text(114, 444, "POLICY + CONTRACTS"),
            rect(90, 566, 1038, 232, "workflow-panel", rx=22),
            panel_text(114, 594, "WORKFLOW GOVERNANCE LAYER"),
            rect(90, 822, 1038, 204, "kernel-panel", rx=22),
            panel_text(114, 850, "INVOCATION GOVERNANCE KERNEL"),
            rect(90, 1050, 1038, 136, "evidence-panel", rx=22),
            panel_text(114, 1078, "EVIDENCE OUTPUTS"),
            rect(1156, 416, 354, 770, "ops-panel", rx=22),
            panel_text(1180, 444, "VALIDATION + OPERATOR SURFACES"),
        ]
    )

    # Policy + contracts
    parts.extend(
        [
            node(114, 454, 220, 62, "node-policy", ["Policy YAML / workflow DSL"]),
            node(354, 454, 170, 62, "node-policy", ["JSON Schemas"]),
            node(544, 454, 170, 62, "node-policy", ["manifests"]),
            node(734, 454, 370, 62, "node-policy", ["policy loading / validation"], ["composition, narrowing, and fail-closed checks"]),
        ]
    )

    # Workflow governance
    parts.extend(
        [
            node(114, 614, 206, 72, "node-workflow", ["AIGC.open_session(...)"]),
            node(344, 614, 206, 72, "node-workflow", ["GovernanceSession"]),
            node(574, 614, 206, 72, "node-workflow", ["SessionPreCallResult"]),
            node(114, 710, 206, 64, "node-workflow", ["AgentIdentity"]),
            node(344, 710, 206, 64, "node-workflow", ["AgentCapabilityManifest"]),
            node(
                574,
                706,
                530,
                72,
                "node-workflow",
                ["handoffs, budgets, escalation checkpoints"],
                ["session / workflow evidence correlation"],
            ),
        ]
    )

    # Kernel
    kernel_x = [114, 316, 518, 720, 922]
    kernel_titles = [
        ["unified + split", "enforcement"],
        ["ordered gates"],
        ["pre-call", "authorization"],
        ["post-call output", "validation"],
        ["risk"],
    ]
    for x, title_lines in zip(kernel_x, kernel_titles, strict=True):
        parts.append(node(x, 868, 180, 72, "node-kernel", title_lines))
    parts.append(
        text_box(
            114,
            964,
            988,
            42,
            "node-kernel",
            [
                "pre_authorization -> guards -> role -> preconditions -> tools -> post_authorization -> pre_output -> schema -> postconditions -> post_output -> risk"
            ],
        )
    )

    # Evidence outputs
    parts.extend(
        [
            node(114, 1094, 228, 64, "node-evidence", ["invocation artifacts"]),
            node(364, 1094, 228, 64, "node-evidence", ["workflow artifacts"]),
            node(614, 1094, 228, 64, "node-evidence", ["AuditSink + signing"]),
            node(864, 1094, 238, 64, "node-evidence", ["operator exports"]),
        ]
    )

    # Operator / validation column
    parts.extend(
        [
            node(1182, 470, 302, 80, "node-ops", ["ValidatorHook"], ["typed, versioned extension contract"]),
            node(1182, 584, 302, 72, "node-ops", ["workflow lint"], ["schema, transitions, bindings, budgets"]),
            node(1182, 682, 302, 72, "node-ops", ["workflow trace"], ["timeline reconstruction from emitted evidence"]),
            node(1182, 780, 302, 72, "node-ops", ["workflow export"], ["operator-facing export modes"]),
            note_node(
                1182,
                888,
                302,
                104,
                ["Operator tooling sits beside runtime semantics, not inside the execution path."],
                ["The host still performs provider, tool, and transport interactions."],
            ),
            note_node(
                1182,
                1024,
                302,
                112,
                ["Trace and export consume emitted invocation and workflow evidence."],
                ["Optional adapters remain optional normalization layers."],
            ),
        ]
    )

    # Connectors
    parts.extend(
        [
            path("M225 184 V228 H1074 V264"),
            path("M350 292 H676"),
            path("M630 292 H676"),
            path("M1074 326 V742 H1104", muted=True),
            path("M919 516 V566"),
            path("M839 778 V822"),
            path("M653 1026 V1050"),
            path("M1104 486 H1140 V510 H1182"),
            path("M1104 742 H1140 V620 H1182"),
            path("M1102 1126 H1140 V1080 H1182", muted=True),
        ]
    )

    # Footer notes
    parts.extend(
        [
            lines_text(
                60,
                1240,
                [("footer-note", "AIGC remains an SDK, not a hosted runtime or orchestrator.")],
                anchor="start",
            ),
            lines_text(
                60,
                1262,
                [("footer-note", "Provider, tool, and transport interactions remain host-owned.")],
                anchor="start",
            ),
            lines_text(
                60,
                1282,
                [("footer-small", "Workflow governance wraps invocation governance. Optional adapters normalize evidence into governance events; they do not replace the core.")],
                anchor="start",
            ),
        ]
    )
    parts.append(footer())
    return "".join(parts)


def write_svg(path: Path, content: str) -> None:
    path.write_text(content + "\n", encoding="utf-8")


def main() -> None:
    diagrams_dir = Path(__file__).resolve().parent
    repo_root = diagrams_dir.parents[2]
    demo_dir = repo_root / "demo-app-react" / "public" / "diagrams"

    beta_light = render_beta(LIGHT)
    beta_dark = render_beta(DARK)
    full_light = render_full(LIGHT)
    full_dark = render_full(DARK)

    outputs = {
        diagrams_dir / "aigc_v090_beta_component_light.svg": beta_light,
        diagrams_dir / "aigc_v090_beta_component_dark.svg": beta_dark,
        diagrams_dir / "aigc_v090_full_component_light.svg": full_light,
        diagrams_dir / "aigc_v090_full_component_dark.svg": full_dark,
        diagrams_dir / "aigc_architecture_component_light.svg": beta_light,
        diagrams_dir / "aigc_architecture_component.svg": beta_dark,
        demo_dir / "aigc_architecture_component_light.svg": beta_light,
        demo_dir / "aigc_architecture_component.svg": beta_dark,
    }

    for path_obj, content in outputs.items():
        write_svg(path_obj, content)


if __name__ == "__main__":
    main()
