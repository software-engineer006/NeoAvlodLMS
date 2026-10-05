# NeoAvlodLMS agent workflow

Read `skills/neoavlod-resume/SKILL.md` and `TASKS.md` before implementing changes.
A request such as "/Users/dulmurod/NeoAvlodLMS/TASKS.md buni bajar" authorizes
continuing the ordered registry from its current active task without recreating it.

Use Docker for application execution, package installation, testing, linting,
type checking, migrations, and Python task-manager execution. File editing,
Git inspection and Docker orchestration may run on the host. Do not fall back
to host Python, Node or the old backend/.venv when Docker fails.

Only one atomic task is active. Keep acceptance evidence and the resume
checkpoint in TASKS.md. Finish and verify that task before starting the next.
Do not mark blocked or untested work complete. Do not delegate simultaneous
implementation of registry tasks. Keep Uzbek task reports concise.

