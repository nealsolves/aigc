"""Implementation of the `aigc policy init` CLI command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aigc._internal.presets import (
    MinimalPreset,
    StandardPreset,
    RegulatedHighAssurancePreset,
)

_PROFILE_PRESETS = {
    "minimal": MinimalPreset,
    "standard": StandardPreset,
    "regulated-high-assurance": RegulatedHighAssurancePreset,
}


def _cmd_policy_init(args: argparse.Namespace) -> int:
    """Run the `aigc policy init` subcommand."""
    output_path = Path(args.output)

    if output_path.exists():
        print(
            f"ERROR: {output_path} already exists. "
            "Remove it or choose a different --output path.",
            file=sys.stderr,
        )
        return 1

    preset_cls = _PROFILE_PRESETS[args.profile]
    preset = preset_cls(role=args.role)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(preset.policy_yaml, encoding="utf-8")
    except OSError as e:
        print(f"ERROR: cannot write {output_path}: {e}", file=sys.stderr)
        return 1

    print(f"Policy written to: {output_path}")
    return 0
