# Import Boundary Refactor Plan

## Goal
Eliminate hexagonal architecture import-boundary violations reported by `scripts/check_imports.py` while preserving behavior.

## Constraints
- Domain must not import application or infrastructure.
- Application must not import infrastructure.
- API must not import infrastructure.
- Use a composition root for wiring (bootstrap).

## Plan Steps
1. Create a composition root (`src/bootstrap/`) for dependency wiring and stub selection. Update API dependency modules to use bootstrap providers instead of importing infrastructure directly.
2. Move correlation utilities from infrastructure to application and update all imports (application services, API middleware/dependencies, infra logging).
3. Remove infrastructure imports from application services by introducing ports/injection and moving protocol compliance checks to tests.
4. Move domain primitives out of application ports (TimeAuthorityProtocol, ReminderMilestone, TaskOperation + role maps). Update all imports to use domain modules.
5. Remove application type hints from domain (ledger export event type) by introducing domain-local protocol/type alias.
6. Introduce application-level metrics port/service and wire metrics middleware/routes via bootstrap (no API → infrastructure imports).
7. Update tests and run `python3 scripts/check_imports.py` to validate boundary compliance.
