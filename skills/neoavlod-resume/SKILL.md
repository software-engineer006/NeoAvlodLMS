---
name: neoavlod-resume
description: Continue NeoAvlodLMS TASKS.md sequentially in Docker from its active task or first unfinished task. Use for implementing this repository's task registry and recovering interrupted sessions.
---

# NeoAvlodLMS resume

Resolve the repository from `AGENTS.md`; its current location is
`/Users/dulmurod/NeoAvlodLMS`. Read `TASKS.md` for architecture, acceptance
criteria, completed evidence and the current checkpoint. It is the maintained
state source; do not ask for old chat history or replace the registry.

1. Run `scripts/agent_skills/docker_env.sh up`. This builds the development
   image, starts PostgreSQL and backend, and waits for health. If Docker is
   unavailable, retain the active task and record the exact blocker. Continue
   independent file work where useful; never substitute host runtime checks.
2. Run `scripts/agent_skills/task.sh resume`. It keeps an existing `[/]` task
   active or selects the first `[ ]`. Work on that task only. Reconcile existing
   files and tests before writing new code; interrupted edits persist.
3. Execute checks via repository helpers: `check_backend.sh`,
   `check_frontend.sh`, `run_migrations.sh`, `check_agent_skills.sh` and
   `docker_env.sh smoke`. They enter Docker automatically. Rebuild with
   `docker_env.sh build` when dependency declarations change. Use
   `docker_env.sh exec <command> [args...]` for other backend commands and
   `docker_env.sh node <command> [args...]` for Node commands. Do not install
   dependencies or execute Python/Node on the host.
4. Check the task's full acceptance criteria. Unit tests alone do not prove
   live Docker, migration, role or notification requirements. DB tests use the
   separate disposable test-database, never the persistent development DB.
5. Only after acceptance passes, run
   `scripts/agent_skills/task.sh done ID --evidence 'commands and results'`.
   Report three concise lines: `[STATUS]`, `[FILES]`, `[NEXT]`; then resume the
   next task while the user's continuing-work authorization applies.

Before a context switch or stopping for a real dependency, update TASKS.md's
checkpoint with active ID, concrete progress, verification results, exact next
command and required external input. Leave the task `[/]` if any acceptance
criterion remains unverified. No placeholders, skipped tests or fake delivery
results count as completed functionality.

Use PostgreSQL 18.6 as currently verified stable. Its named data volume mounts
at `/var/lib/postgresql`. Do not automatically switch majors or delete existing
volumes. Fake Telegram is allowed in tests; real onboarding/delivery requires
the configured bot token. Preserve secrets in ignored environment files;
never copy or print them into evidence, logs, Git or responses.

