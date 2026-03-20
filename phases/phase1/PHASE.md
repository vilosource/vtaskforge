# Phase 1 — Core Models & Basic CRUD

Status: Planning (2026-03-20)

## Goal

All domain models exist in the database with migrations, DRF serializers/viewsets expose CRUD endpoints, and the task state machine enforces valid transitions.

## Scope

- Workplan, Phase, Task, Agent models + migrations
- Link model (generic relationship system)
- Note, Review, TaskEvent models
- Task state machine with transition enforcement
- Basic CRUD endpoints for all models
- Atomic task claiming with conflict handling
- Review flag cascading (task > phase > workplan)

## Tasks

*To be defined — individual task specs will be added to `tasks/` directory.*

## DAG

*To be defined in `dag.yaml`.*
