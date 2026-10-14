---
name: neoavlod-guide-scenes
description: Build crisp NeoAvlodLMS React guide previews with shared components and current Tailwind, synthetic data, step markers and portal/role boundaries; use for replacing screenshot guides.
---

# NeoAvlod React guide scenes

Read `AUDIT_PLAN.md` and the guide task acceptance in TASKS.md. Use Docker for
package changes/builds/tests and Chromium acceptance.

- Render reusable declarative React components with real shared UI atoms, latest
  verified Tailwind and a typed scene
  registry. Reuse form/table/modal layouts; avoid importing live management
  components that fetch or mutate without a presentation-only data boundary.
- All preview identities, counts and forms are synthetic. No production IDs,
  API fallback, tokens, secret placeholders, credential reads or deep links.
  Previews are inert/read-only, including keyboard/form submission.
- Keep numbered markers anchored to semantic scene elements across viewport and
  font sizes. HTML text and SVG icons stay crisp at enlarged zoom; no raster
  screenshot is used for the preview. Provide accessible scene descriptions and
  text steps independently of the visual representation.
- Separate admin and teacher scene entrypoints so teacher bundles do not contain
  superadmin log/bot/grant material. Topic filtering and navigation follow current
  server role rules, including removal of admin/teacher audit visibility.
- Check all topic IDs/step markers, search/zoom/permission revocation, 1440/768/360
  layouts, no overflow/JS errors, and absence of demo network/mutation effects.
  Verify source and committed release checksums after replacing PNG assets.
