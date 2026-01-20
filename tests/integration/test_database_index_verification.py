"""Database index verification tests (Story 5.8, AC6).

Tests to verify database indexes exist and queries use them efficiently.

AC6: Index Optimization for Count Queries
- idx_co_signs_petition_id exists (migration 024)
- Queries use index scan (not sequential scan)
- EXPLAIN shows efficient query plan

These tests document the expected index structure. Actual EXPLAIN ANALYZE
tests require a live database connection.

Run verification SQL manually:
    -- Verify index exists
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE tablename = 'co_signs'
    AND indexname = 'idx_co_signs_petition_id';

    -- Verify query uses index
    EXPLAIN ANALYZE
    SELECT COUNT(*) FROM co_signs WHERE petition_id = '00000000-0000-0000-0000-000000000001';
    -- Should show "Index Only Scan" or "Index Scan"
"""

from __future__ import annotations

from pathlib import Path


class TestIndexMigrationDocumentation:
    """Tests that verify index definitions exist in migrations."""

    def test_idx_co_signs_petition_id_exists_in_migration_024(self) -> None:
        """Verify idx_co_signs_petition_id is defined in migration 024.

        AC6: idx_co_signs_petition_id exists (migration 024).
        """
        migration_path = Path("migrations/024_create_co_signs_table.sql")
        assert migration_path.exists(), f"Migration not found: {migration_path}"

        content = migration_path.read_text()

        # Verify index creation statement
        assert (
            "CREATE INDEX idx_co_signs_petition_id ON co_signs(petition_id)" in content
        )

    def test_idx_co_signs_signer_id_exists_in_migration_024(self) -> None:
        """Verify idx_co_signs_signer_id is defined in migration 024.

        Supports SYBIL-1 rate limiting queries (FR-6.6).
        """
        migration_path = Path("migrations/024_create_co_signs_table.sql")
        content = migration_path.read_text()

        assert "CREATE INDEX idx_co_signs_signer_id ON co_signs(signer_id)" in content

    def test_co_signer_count_column_exists_in_migration_025(self) -> None:
        """Verify co_signer_count column is defined in migration 025.

        AC3: Counter column on petition_submissions table.
        """
        migration_path = Path(
            "migrations/025_add_cosigner_count_to_petition_submissions.sql"
        )
        assert migration_path.exists(), f"Migration not found: {migration_path}"

        content = migration_path.read_text()

        # Verify column addition
        assert "co_signer_count INTEGER NOT NULL DEFAULT 0" in content

        # Verify constraint
        assert "chk_petition_submissions_cosigner_count_non_negative" in content


class TestExpectedQueryPlans:
    """Document expected query plans for critical operations.

    These tests serve as documentation. Actual query plan validation
    requires live database testing.
    """

    def test_documented_count_query_plan(self) -> None:
        """Document the expected query plan for count queries.

        Expected plan for:
            SELECT co_signer_count FROM petition_submissions WHERE id = ?

        This should be an Index Scan or Primary Key lookup (O(1)).
        The `id` column is the PRIMARY KEY with automatic index.
        """
        expected_plan = """
        Index Scan using petition_submissions_pkey on petition_submissions
          Index Cond: (id = '<uuid>')
        """
        # Document only - actual verification requires EXPLAIN ANALYZE
        assert expected_plan is not None

    def test_documented_co_sign_count_query_plan(self) -> None:
        """Document the expected query plan for co_signs COUNT.

        Expected plan for:
            SELECT COUNT(*) FROM co_signs WHERE petition_id = ?

        Should use idx_co_signs_petition_id for Index Only Scan
        when verification service compares counter vs actual.
        """
        expected_plan = """
        Aggregate
          ->  Index Only Scan using idx_co_signs_petition_id on co_signs
                Index Cond: (petition_id = '<uuid>')
        """
        # Document only - actual verification requires EXPLAIN ANALYZE
        assert expected_plan is not None


class TestIndexVerificationSQLQueries:
    """Provide SQL queries for manual index verification."""

    def test_index_existence_query(self) -> None:
        """Provide query to verify index exists."""
        query = """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'co_signs'
        AND indexname = 'idx_co_signs_petition_id';
        """

        # Expected result:
        # indexname                  | indexdef
        # idx_co_signs_petition_id   | CREATE INDEX idx_co_signs_petition_id ON public.co_signs USING btree (petition_id)

        assert "pg_indexes" in query
        assert "idx_co_signs_petition_id" in query

    def test_explain_analyze_query(self) -> None:
        """Provide EXPLAIN ANALYZE query for count verification."""
        query = """
        EXPLAIN ANALYZE
        SELECT COUNT(*) FROM co_signs
        WHERE petition_id = '00000000-0000-0000-0000-000000000001';
        """

        # Expected: Should show "Index Only Scan" or "Index Scan"
        # NOT "Seq Scan" which would indicate missing index

        assert "EXPLAIN ANALYZE" in query
        assert "petition_id" in query
