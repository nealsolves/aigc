"""Implementation of the `aigc workflow init` CLI command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aigc._internal.errors import WorkflowStarterIntegrityError
from aigc._internal.starter_templates import (
    render_minimal_starter,
    render_standard_starter,
    render_regulated_starter,
)

_PROFILE_RENDERERS = {
    "minimal": render_minimal_starter,
    "standard": render_standard_starter,
    "regulated-high-assurance": render_regulated_starter,
}


def generate_starter(profile: str, output_dir: Path, role: str = "ai-assistant") -> None:
    """Generate starter files for `profile` into `output_dir`.

    Raises WorkflowStarterIntegrityError if any target file already exists.
    Raises OSError if the directory cannot be created or files cannot be written.
    """
    render_fn = _PROFILE_RENDERERS[profile]
    files = render_fn(role=role)

    conflicts = [name for name in files if (output_dir / name).exists()]
    if conflicts:
        raise WorkflowStarterIntegrityError(
            f"Cannot generate starter -- file(s) already exist in {output_dir}: "
            + ", ".join(conflicts),
            details={"profile": profile, "conflicts": conflicts},
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (output_dir / name).write_text(content, encoding="utf-8")


def _cmd_workflow_init(args: argparse.Namespace) -> int:
    """Run the `aigc workflow init` subcommand."""
    output_dir = Path(args.output_dir)
    profile = args.profile

    try:
        generate_starter(profile, output_dir, role=args.role)
    except WorkflowStarterIntegrityError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"ERROR: cannot write to {output_dir}: {e}", file=sys.stderr)
        return 1

    print(f"Generated {profile} starter in {output_dir}/")
    for name in _PROFILE_RENDERERS[profile](role=args.role):
        print(f"  {name}")
    return 0
