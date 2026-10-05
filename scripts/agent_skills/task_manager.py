#!/usr/bin/env python3
"""Validate and atomically advance the single-task TASKS.md state machine."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TASK_LINE = re.compile(r"^- \[([^\]]*)\] (\d{3}) — (.+)$")


class TaskError(ValueError):
    pass


@dataclass(frozen=True)
class Task:
    id: str
    status: str
    title: str
    line: int


def parse(document: str) -> list[Task]:
    tasks: list[Task] = []
    for index, line in enumerate(document.splitlines()):
        if not line.startswith("- ["):
            continue
        match = TASK_LINE.fullmatch(line)
        if match is None or match[1] not in (" ", "/", "x"):
            raise TaskError(f"Noto‘g‘ri task formati: {index + 1}-qator")
        tasks.append(Task(match[2], match[1], match[3], index))
    if not tasks:
        raise TaskError("Tasklar topilmadi")
    if [task.id for task in tasks] != [f"{n:03d}" for n in range(1, len(tasks) + 1)]:
        raise TaskError("Task IDlari 001 dan ketma-ket va takrorsiz bo‘lishi kerak")
    unfinished = False
    active = False
    for task in tasks:
        if task.status == "x":
            if unfinished:
                raise TaskError("Bajarilgan task bajarilmagan taskdan keyin joylashgan")
        elif task.status == "/":
            if active or unfinished:
                raise TaskError("Faqat birinchi bajarilmagan task faol bo‘lishi mumkin")
            active = unfinished = True
        else:
            unfinished = True
    return tasks


def atomic_write(path: Path, document: str) -> None:
    mode = path.stat().st_mode & 0o777
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = stream.name
            os.chmod(temporary, mode)
            stream.write(document)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)


def transition(path: Path, command: str, task_id: str | None, evidence: str | None) -> Task | None:
    # Lock a stable sibling file: locking TASKS.md itself fails after os.replace.
    with path.with_name(f".{path.name}.lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        document = path.read_text(encoding="utf-8")
        tasks = parse(document)
        pending = next((task for task in tasks if task.status != "x"), None)
        if pending is None:
            if command == "resume":
                return None
            raise TaskError("Barcha tasklar yakunlangan")
        if task_id is not None and task_id != pending.id:
            raise TaskError(f"Faqat birinchi bajarilmagan task: {pending.id}")
        if command == "resume" and pending.status == "/":
            return pending
        lines = document.splitlines(keepends=True)
        if command in ("start", "resume"):
            if pending.status == "/":
                raise TaskError(f"Task {pending.id} allaqachon faol")
            lines[pending.line] = lines[pending.line].replace("- [ ]", "- [/]", 1)
        else:
            if pending.status != "/":
                raise TaskError("Yakunlashdan oldin taskni boshlash kerak")
            if not evidence or not evidence.strip() or any(c in evidence for c in "\r\n"):
                raise TaskError("Bir qatorli, bo‘sh bo‘lmagan --evidence kerak")
            end = next((task.line for task in tasks if task.line > pending.line), len(lines))
            evidence_lines = [n for n in range(pending.line + 1, end) if lines[n].startswith("  - Dalil: ")]
            if len(evidence_lines) != 1:
                raise TaskError("Task uchun aynan bitta Dalil qatori kerak")
            lines[evidence_lines[0]] = f"  - Dalil: {evidence.strip()}\n"
            lines[pending.line] = lines[pending.line].replace("- [/]", "- [x]", 1)
        updated = "".join(lines)
        parsed = parse(updated)
        atomic_write(path, updated)
        return next(task for task in parsed if task.id == pending.id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=ROOT / "TASKS.md")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    commands.add_parser("list")
    commands.add_parser("next")
    commands.add_parser("resume")
    start = commands.add_parser("start")
    start.add_argument("id")
    done = commands.add_parser("done")
    done.add_argument("id")
    done.add_argument("--evidence", required=True)
    args = parser.parse_args()
    try:
        if os.environ.get("NEOAVLOD_IN_DOCKER") != "1":
            raise TaskError("task.sh orqali Dockerda ishga tushiring; host Python taqiqlangan")
        path = args.file.resolve()
        if args.command in ("start", "done", "resume"):
            task = transition(path, args.command, getattr(args, "id", None), getattr(args, "evidence", None))
            print("Barcha tasklar yakunlangan" if task is None else f"[{task.status}] {task.id} — {task.title}")
        else:
            tasks = parse(path.read_text(encoding="utf-8"))
            if args.command == "validate":
                print(f"OK: {len(tasks)} task, {sum(t.status == 'x' for t in tasks)} bajarilgan")
            elif args.command == "list":
                print(json.dumps([{"id": t.id, "status": t.status, "title": t.title} for t in tasks], ensure_ascii=False))
            else:
                task = next((t for t in tasks if t.status != "x"), None)
                print("Barcha tasklar yakunlangan" if task is None else f"[{task.status}] {task.id} — {task.title}")
        return 0
    except (OSError, TaskError) as error:
        print(f"Xato: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
