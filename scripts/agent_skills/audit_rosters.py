"""Read-only CSV inventory; preserve cells, provenance and unresolved data privately."""

import csv
import hashlib
import json
import os
from pathlib import Path
import re

SOURCE = Path("/workspace/.private/real-data/source")
OUTPUT = SOURCE.parent / "audit.json"


def main() -> None:
    if os.environ.get("NEOAVLOD_IN_DOCKER") != "1":
        raise RuntimeError("Docker required")
    report: dict[str, object] = {}
    for path in sorted(SOURCE.glob("*.csv")):
        data = path.read_bytes()
        rows = list(csv.reader(data.decode("utf-8-sig").splitlines()))
        names: dict[str, list[int]] = {}
        records = []
        other = []
        sections = []
        section = None
        for number, row in enumerate(rows, 1):
            row += [""] * max(0, 6 - len(row))
            name = " ".join(row[3].split())
            if name and re.search(r"toq|juft", row[4], re.IGNORECASE):
                section = {"row": number, "name": name, "days_raw": row[4],
                           "time_raw": row[5], "header_cells": row}
                sections.append(section)
                continue
            if not name or name.casefold() == "ism":
                continue
            # A header is not a pupil. A nonempty cell remains reviewable.
            if (section is None or len(name.split()) < 2
                    or name.casefold().startswith("boshqa guruhga")
                    or not re.search(r"[a-zA-ZА-Яа-я]", name)):
                other.append({"row": number, "cells": row})
                continue
            names.setdefault(name.casefold(), []).append(number)
            digits = re.sub(r"\D", "", row[4])
            phone = ("+998" + digits) if len(digits) == 9 else (
                "+" + digits if len(digits) == 12 and digits.startswith("998") else None
            )
            records.append({"row": number, "name": name, "phone": phone,
                            "grade": row[5].strip() or None, "cells": row,
                            "section_row": section["row"], "section_name": section["name"],
                            "issues": ([] if phone else ["phone_missing_or_ambiguous"])})
        summary = {"physical_rows": len(rows), "candidates": len(records),
                   "missing_or_ambiguous_phone": sum(r["phone"] is None for r in records),
                   "duplicate_names": {k: v for k, v in names.items() if len(v) > 1},
                   "other_nonempty_name_cells": len(other)}
        report[path.name] = {"sha256": hashlib.sha256(data).hexdigest(),
                             "summary": summary, "records": records, "other": other,
                             "raw_rows": rows}
        report[path.name]["sections"] = sections
        print(path.name, json.dumps({**summary, "sections": [
            {"row": s["row"], "name": s["name"], "time_raw": s["time_raw"],
             "students": sum(r["section_row"] == s["row"] for r in records)}
            for s in sections]}, ensure_ascii=False))
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT.chmod(0o600)


if __name__ == "__main__":
    main()
