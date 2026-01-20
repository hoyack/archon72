"""Integration tests for realms schema (Story 0.6, HP-3, HP-4).

Tests:
- Migration 015 creates realms table with correct schema
- Migration creates sentinel_realm_mappings table
- Seed data populates 9 canonical realms
- Default sentinel mappings are created
- Constraints enforce validation rules
"""

import pytest

from tests.integration.conftest import IntegrationTestBase


@pytest.mark.integration
class TestRealmsSchema(IntegrationTestBase):
    """Test realms table schema and constraints."""

    async def test_realms_table_exists(self) -> None:
        """AC1: realms table exists after migration."""
        result = await self.client.table("realms").select("id").limit(1).execute()
        # Should not raise exception
        assert result is not None

    async def test_realms_table_columns(self) -> None:
        """AC1: realms table has all required columns."""
        result = await self.client.table("realms").select("*").limit(1).execute()

        if result.data:
            row = result.data[0]
            # Check all required columns exist
            assert "id" in row
            assert "name" in row
            assert "display_name" in row
            assert "knight_capacity" in row
            assert "status" in row
            assert "description" in row
            assert "created_at" in row
            assert "updated_at" in row

    async def test_nine_canonical_realms_seeded(self) -> None:
        """AC2: 9 canonical realms are seeded."""
        result = await self.client.table("realms").select("name").execute()

        assert len(result.data) >= 9

        realm_names = {row["name"] for row in result.data}
        expected_realms = {
            "realm_privacy_discretion_services",
            "realm_relationship_facilitation",
            "realm_knowledge_skill_development",
            "realm_predictive_analytics_forecasting",
            "realm_character_virtue_development",
            "realm_accurate_guidance_counsel",
            "realm_threat_anomaly_detection",
            "realm_personality_charisma_enhancement",
            "realm_talent_acquisition_team_building",
        }

        assert expected_realms.issubset(realm_names)

    async def test_canonical_realms_are_active(self) -> None:
        """AC2: All canonical realms have ACTIVE status."""
        result = (
            await self.client.table("realms")
            .select("name, status")
            .eq("status", "ACTIVE")
            .execute()
        )

        assert len(result.data) >= 9

    async def test_canonical_realms_have_default_capacity(self) -> None:
        """AC2: Canonical realms have knight_capacity = 5."""
        result = (
            await self.client.table("realms").select("name, knight_capacity").execute()
        )

        for row in result.data:
            assert row["knight_capacity"] == 5

    async def test_realm_name_unique_constraint(self) -> None:
        """AC3: Duplicate realm names are rejected."""
        # Try to insert duplicate name
        with pytest.raises(Exception):  # Will raise on conflict
            await (
                self.client.table("realms")
                .insert(
                    {
                        "name": "realm_privacy_discretion_services",
                        "display_name": "Duplicate Realm",
                        "knight_capacity": 5,
                    }
                )
                .execute()
            )

    async def test_realm_status_constraint(self) -> None:
        """AC3: Invalid status values are rejected."""
        with pytest.raises(Exception):
            await (
                self.client.table("realms")
                .insert(
                    {
                        "name": "test_invalid_status_realm",
                        "display_name": "Test Realm",
                        "knight_capacity": 5,
                        "status": "INVALID_STATUS",
                    }
                )
                .execute()
            )

    async def test_realm_knight_capacity_min_constraint(self) -> None:
        """AC3: knight_capacity < 1 is rejected."""
        with pytest.raises(Exception):
            await (
                self.client.table("realms")
                .insert(
                    {
                        "name": "test_min_capacity_realm",
                        "display_name": "Test Realm",
                        "knight_capacity": 0,
                    }
                )
                .execute()
            )

    async def test_realm_knight_capacity_max_constraint(self) -> None:
        """AC3: knight_capacity > 100 is rejected."""
        with pytest.raises(Exception):
            await (
                self.client.table("realms")
                .insert(
                    {
                        "name": "test_max_capacity_realm",
                        "display_name": "Test Realm",
                        "knight_capacity": 101,
                    }
                )
                .execute()
            )


@pytest.mark.integration
class TestSentinelRealmMappingsSchema(IntegrationTestBase):
    """Test sentinel_realm_mappings table schema (HP-4)."""

    async def test_sentinel_realm_mappings_table_exists(self) -> None:
        """HP-4: sentinel_realm_mappings table exists."""
        result = (
            await self.client.table("sentinel_realm_mappings")
            .select("id")
            .limit(1)
            .execute()
        )
        # Should not raise exception
        assert result is not None

    async def test_sentinel_realm_mappings_columns(self) -> None:
        """HP-4: sentinel_realm_mappings has all required columns."""
        result = (
            await self.client.table("sentinel_realm_mappings")
            .select("*")
            .limit(1)
            .execute()
        )

        if result.data:
            row = result.data[0]
            assert "id" in row
            assert "sentinel_type" in row
            assert "realm_id" in row
            assert "priority" in row
            assert "created_at" in row
            assert "updated_at" in row

    async def test_default_sentinel_mappings_exist(self) -> None:
        """HP-4: Default sentinel mappings are seeded."""
        result = (
            await self.client.table("sentinel_realm_mappings")
            .select("sentinel_type")
            .execute()
        )

        sentinel_types = {row["sentinel_type"] for row in result.data}

        # At least some default mappings should exist
        expected_types = {
            "privacy",
            "security",
            "learning",
            "guidance",
            "team",
            "general",
        }
        assert expected_types.issubset(sentinel_types)

    async def test_sentinel_mapping_references_valid_realm(self) -> None:
        """HP-4: Sentinel mappings reference valid realm IDs."""
        mappings = (
            await self.client.table("sentinel_realm_mappings")
            .select("realm_id")
            .execute()
        )

        for mapping in mappings.data:
            realm_id = mapping["realm_id"]
            realm = (
                await self.client.table("realms")
                .select("id")
                .eq("id", realm_id)
                .execute()
            )
            assert len(realm.data) == 1

    async def test_sentinel_mapping_unique_constraint(self) -> None:
        """HP-4: Duplicate sentinel_type + realm_id is rejected."""
        # Get an existing mapping
        existing = (
            await self.client.table("sentinel_realm_mappings")
            .select("sentinel_type, realm_id")
            .limit(1)
            .execute()
        )

        if existing.data:
            mapping = existing.data[0]
            with pytest.raises(Exception):
                await (
                    self.client.table("sentinel_realm_mappings")
                    .insert(
                        {
                            "sentinel_type": mapping["sentinel_type"],
                            "realm_id": mapping["realm_id"],
                            "priority": 99,
                        }
                    )
                    .execute()
                )


@pytest.mark.integration
class TestRealmsIndexes(IntegrationTestBase):
    """Test that indexes support efficient queries."""

    async def test_query_by_status_efficient(self) -> None:
        """Index supports efficient status queries."""
        # Should execute quickly with index
        result = (
            await self.client.table("realms")
            .select("*")
            .eq("status", "ACTIVE")
            .execute()
        )

        assert len(result.data) >= 9

    async def test_query_by_name_efficient(self) -> None:
        """Index supports efficient name lookups."""
        result = (
            await self.client.table("realms")
            .select("*")
            .eq("name", "realm_privacy_discretion_services")
            .execute()
        )

        assert len(result.data) == 1

    async def test_query_sentinel_by_type_efficient(self) -> None:
        """Index supports efficient sentinel type lookups."""
        result = (
            await self.client.table("sentinel_realm_mappings")
            .select("*")
            .eq("sentinel_type", "privacy")
            .execute()
        )

        # Should find at least one mapping
        assert len(result.data) >= 1
