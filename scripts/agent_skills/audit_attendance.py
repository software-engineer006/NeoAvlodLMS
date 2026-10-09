"""Audit reviewed legacy CSV attendance without embedding private student data in code."""

import argparse
import json
import os
from pathlib import Path

from neoavlod.attendance_import import build_attendance_plan, compute_plan_hash
from neoavlod.real_staff import private_write


def main() -> None:
    if os.environ.get("NEOAVLOD_IN_DOCKER") != "1":
        raise RuntimeError("Docker required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Path("/workspace/educenter_data")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/workspace/.private/real-data/attendance-plan.json"),
    )
    args = parser.parse_args()
    plan = build_attendance_plan(args.source)
    private_write(args.output, json.dumps(plan, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "summary": plan["summary"],
                "plan_sha256": compute_plan_hash(plan),
                "report": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
