# Phase 6 — Task Spec Storage

Store the full task implementation spec in the database so agents can retrieve
it via the API and humans can inspect it in the web UI. Currently, specs live
as YAML files on the filesystem and are discarded after import.

This phase adds five new fields to the Task model (`spec`, `agent_model`,
`test_command`, `judge`, `isolation`), updates the import pipeline to store them,
exposes them in the API and web UI, and re-imports Phase 5 as the first workplan
with specs stored in the DB.
