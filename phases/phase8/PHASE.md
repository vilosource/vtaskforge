# Phase 8 — Rename Phase to Milestone

Mechanical rename of "Phase" to "Milestone" across the entire codebase.
This is a prerequisite for the project hierarchy feature (Phase 9) and
must be completed and fully verified before any new model changes begin.

The rename touches ~1,666 occurrences across 82 files spanning backend,
tests, CLI, web UI, docs, and agent prompts. It must be atomic per layer
to avoid partial renames that break tests.

The phase ends with a full regression test, dogfood rebuild, and visual
verification that the UI renders correctly with the new terminology.
