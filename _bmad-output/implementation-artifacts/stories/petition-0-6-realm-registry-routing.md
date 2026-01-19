# Story 0.6: Realm Registry & Routing

**Epic:** Petition Epic 0 - Foundation & Migration
**Priority:** P0
**Status:** Done
**Completed:** 2026-01-19

## User Story

As a **developer**,
I want a realm registry with valid routing targets,
So that petitions can be referred to appropriate Knights by realm.

## Acceptance Criteria

### AC1: Realms Table Created ✅
- [x] Migration 015 creates `realms` table with correct schema
- [x] Columns: `id` (UUID), `name` (text, unique), `display_name`, `knight_capacity`, `status`, `description`, `created_at`, `updated_at`
- [x] Constraints enforce validation rules (name length, capacity range, valid status)

### AC2: Canonical Realms Seeded ✅
- [x] 9 canonical realms from archons-base.json are seeded
- [x] All realms have ACTIVE status
- [x] Default knight_capacity = 5

### AC3: RealmRegistry Service ✅
- [x] `RealmRegistryProtocol` defines the contract
- [x] `RealmRegistryService` implements Supabase queries
- [x] Methods: `get_realm_by_id`, `get_realm_by_name`, `list_active_realms`, `get_realms_for_sentinel`, `get_default_realm`, `is_realm_available`, `get_realm_knight_capacity`

### AC4: Sentinel-to-Realm Mapping (HP-4) ✅
- [x] `sentinel_realm_mappings` table created
- [x] Links sentinel types to realms with priority ordering
- [x] Default mappings seeded: privacy, security, learning, guidance, team, general

### AC5: Testing Support ✅
- [x] `RealmRegistryStub` provides in-memory implementation
- [x] Pre-populated with canonical realms
- [x] Configurable sentinel mappings
- [x] Operation tracking for test assertions

## Constitutional Constraints

- **HP-3:** Realm registry for valid petition routing targets
- **HP-4:** Sentinel-to-realm mapping for petition triage
- **NFR-7.3:** Knight capacity limits per realm

## Implementation Details

### Files Created

#### Domain Model
- `src/domain/models/realm.py` - Realm entity with RealmStatus enum, validation, and canonical realm IDs

#### Migration
- `migrations/015_create_realms_table.sql` - Creates realms and sentinel_realm_mappings tables with seed data

#### Protocol (Port)
- `src/application/ports/realm_registry.py` - RealmRegistryProtocol interface

#### Service
- `src/application/services/realm_registry.py` - RealmRegistryService (Supabase implementation)

#### Stub
- `src/infrastructure/stubs/realm_registry_stub.py` - In-memory stub for testing

#### Tests
- `tests/unit/domain/models/test_realm.py` - Unit tests for Realm domain model
- `tests/unit/infrastructure/stubs/test_realm_registry_stub.py` - Unit tests for stub
- `tests/integration/test_realms_schema.py` - Integration tests for migration

### Canonical Realms (from archons-base.json)

| Realm ID | Display Name |
|----------|--------------|
| `realm_privacy_discretion_services` | Privacy & Discretion Services |
| `realm_relationship_facilitation` | Relationship Facilitation |
| `realm_knowledge_skill_development` | Knowledge & Skill Development |
| `realm_predictive_analytics_forecasting` | Predictive Analytics & Forecasting |
| `realm_character_virtue_development` | Character & Virtue Development |
| `realm_accurate_guidance_counsel` | Accurate Guidance & Counsel |
| `realm_threat_anomaly_detection` | Threat & Anomaly Detection |
| `realm_personality_charisma_enhancement` | Personality & Charisma Enhancement |
| `realm_talent_acquisition_team_building` | Talent Acquisition & Team Building |

### Default Sentinel Mappings

| Sentinel Type | Target Realm |
|--------------|--------------|
| privacy | realm_privacy_discretion_services |
| security | realm_threat_anomaly_detection |
| learning | realm_knowledge_skill_development |
| guidance | realm_accurate_guidance_counsel |
| team | realm_talent_acquisition_team_building |
| general | All active realms (lowest priority) |

## References

- **HP-3:** Hidden Prerequisite - Realm Registry
- **HP-4:** Hidden Prerequisite - Sentinel-to-realm mapping
- **NFR-7.3:** Knight capacity limits

## Notes

- Knight capacity defaults to 5, representing max concurrent referrals per realm
- RealmStatus supports ACTIVE, INACTIVE, and DEPRECATED states
- Sentinel mappings use priority ordering (lower = higher priority)
- All syntax checks pass; full test execution requires Python 3.11+
