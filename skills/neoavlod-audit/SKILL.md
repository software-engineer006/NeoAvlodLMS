---
name: neoavlod-audit
description: Implement and verify NeoAvlodLMS employee audit capture, immutable archives and superadmin-only log exports; use for audit schema, auth attribution, archive workers, API and deployment changes.
---

# NeoAvlod audit

Read `AUDIT_PLAN.md` and the active TASKS.md acceptance criteria. Run application,
Python and Node work in Docker through the existing repository helpers.

- Capture business deltas in the business transaction. Bind actor context only
  from verified server identity; preserve it when the session starts another
  transaction. Auth, Telegram, migrations and workers need truthful provenance.
- One whitelist/action registry drives capture. Never serialize entire ORM rows,
  request bodies, cookies, query strings, credentials or capability links. Hidden
  credential changes can record that a change happened, never their values.
- Audit reads/exports are role-only superadmin checks, not permission grants.
  Include full-grant admin, teacher and old attendance audit endpoints in denial
  tests. Ordinary attendance history is a separate business view.
- Protect audit schema from runtime UPDATE/DELETE/TRUNCATE. Trusted pruning needs
  a separate archive role and exact verified persisted event IDs; API superadmin
  cannot invoke archive maintenance. Keep archive actor/entity snapshots free
  of cascading business FKs.
- Treat disk as fallible: immutable new-file creation, no symlinks, bounded
  batches, fsync, authenticated encryption and read-back verification precede
  metadata commit/pruning. Do not advance a sequence watermark past concurrently
  uncommitted events. Retry/orphan recovery cannot lose or duplicate an event.
- API archive mount is read-only, outside the web root. Archive files/keys and
  audit schema survive redeploy and business rollback. No delete/export-retention
  endpoint or UI. Distinguish app-role immutability from root/DB-owner powers.
- Verify with isolated PostgreSQL, temporary archive directories and fake
  Telegram. Exercise real role separation, mutation rollback, auth attribution,
  UTC/Tashkent seconds, crash/corruption/traversal, and bounded export memory.
  Record exact results in TASKS.md; synthetic traffic is not live staff evidence.
