#!/usr/bin/env python3
"""Validate archons-base.json against requirements R-1 through R-10.

This script enforces the governance schema requirements for the Archon 72
configuration file, ensuring all constitutional fields are properly defined
for each rank and branch.

Usage:
    python scripts/validate_archons_base.py [--strict]

Options:
    --strict    Fail on count warnings (Duke=21, Earl=3, Marquis>=20)

Exit codes:
    0 - All validations pass
    1 - Validation errors found
"""

import json
import re
import sys
from pathlib import Path
from typing import Any


class ArchonValidator:
    """Validates archons-base.json against governance requirements."""

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        """Record a validation error."""
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        """Record a validation warning."""
        self.warnings.append(msg)

    def validate(self, data: dict[str, Any]) -> bool:
        """Run all validations. Returns True if valid."""
        self.validate_r1_manifest_metadata(data)
        self.validate_r2_constitutional_fields(data)
        self.validate_r3_king_realms(data)
        self.validate_r4_president_portfolios(data)
        self.validate_r5_duke_earl_domains(data)
        self.validate_r6_prince_judicial(data)
        self.validate_r7_marquis_advisory(data)
        self.validate_r8_knight_witness(data)
        self.validate_r9_safety_language(data)
        self.validate_r10_counts(data)
        self.validate_cross_references(data)
        self.validate_governance_matrix(data)

        return len(self.errors) == 0 and (not self.strict or len(self.warnings) == 0)

    def validate_r1_manifest_metadata(self, data: dict[str, Any]) -> None:
        """R-1: Manifest metadata requirements."""
        required = [
            "version",
            "governance_prd_version",
            "last_updated_at",
            "source_of_truth",
        ]
        for field in required:
            if field not in data:
                self.error(f"R-1: Missing manifest field '{field}'")

    def validate_r2_constitutional_fields(self, data: dict[str, Any]) -> None:
        """R-2: Normalized constitutional fields per archon."""
        required_common = [
            "id",
            "name",
            "rank",
            "aegis_rank",
            "rank_level",
            "branch",
            "constitutional_role",
            "governance_permissions",
            "governance_prohibitions",
            "elevenlabs_voice_id",  # Voice binding for TTS
        ]

        for archon in data.get("archons", []):
            name = archon.get("name", "UNKNOWN")
            for field in required_common:
                if field not in archon:
                    self.error(f"R-2: {name} missing required field '{field}'")

    def validate_r3_king_realms(self, data: dict[str, Any]) -> None:
        """R-3: King realm assignments."""
        kings = [a for a in data.get("archons", []) if a.get("rank") == "King"]
        realms = data.get("realms", [])

        # R-3.1: Exactly 9 Kings
        if len(kings) != 9:
            self.error(f"R-3.1: Expected 9 Kings, found {len(kings)}")

        # R-3.2: Each King has realm fields
        king_realm_ids: set[str] = set()
        for king in kings:
            name = king.get("name", "UNKNOWN")
            for field in ["realm_id", "realm_label", "realm_scope"]:
                if field not in king:
                    self.error(f"R-3.2: King {name} missing '{field}'")
            if "realm_id" in king:
                king_realm_ids.add(king["realm_id"])

        # R-3.3: Realms array has exactly 9
        if len(realms) != 9:
            self.error(f"R-3.3: Expected 9 realms, found {len(realms)}")

        # R-3.4: No duplicate realm_id
        realm_ids = [a.get("realm_id") for a in kings if a.get("realm_id")]
        if len(realm_ids) != len(set(realm_ids)):
            self.error("R-3.4: Duplicate realm_id found among Kings")

    def validate_r4_president_portfolios(self, data: dict[str, Any]) -> None:
        """R-4: President portfolio assignments."""
        presidents = [
            a for a in data.get("archons", []) if a.get("rank") == "President"
        ]
        portfolios = data.get("portfolios", [])

        # R-4.1: Exactly 11 Presidents
        if len(presidents) != 11:
            self.error(f"R-4.1: Expected 11 Presidents, found {len(presidents)}")

        # R-4.2: Each President has portfolio fields
        for pres in presidents:
            name = pres.get("name", "UNKNOWN")
            for field in ["portfolio_id", "portfolio_label", "portfolio_scope"]:
                if field not in pres:
                    self.error(f"R-4.2: President {name} missing '{field}'")

        # R-4.3: Portfolios array has exactly 11
        if len(portfolios) != 11:
            self.error(f"R-4.3: Expected 11 portfolios, found {len(portfolios)}")

        # R-4.4: No duplicate portfolio_id
        portfolio_ids = [
            a.get("portfolio_id") for a in presidents if a.get("portfolio_id")
        ]
        if len(portfolio_ids) != len(set(portfolio_ids)):
            self.error("R-4.4: Duplicate portfolio_id found among Presidents")

    def validate_r5_duke_earl_domains(self, data: dict[str, Any]) -> None:
        """R-5: Duke/Earl execution domains."""
        dukes = [a for a in data.get("archons", []) if a.get("rank") == "Duke"]
        earls = [a for a in data.get("archons", []) if a.get("rank") == "Earl"]

        # R-5.1: Dukes have execution_domains
        for duke in dukes:
            name = duke.get("name", "UNKNOWN")
            if "execution_domains" not in duke:
                self.error(f"R-5.1: Duke {name} missing 'execution_domains'")

        # R-5.2: Earls have execution_domains and max_concurrent_tasks
        for earl in earls:
            name = earl.get("name", "UNKNOWN")
            if "execution_domains" not in earl:
                self.error(f"R-5.2: Earl {name} missing 'execution_domains'")
            if "max_concurrent_tasks" not in earl:
                self.error(f"R-5.2: Earl {name} missing 'max_concurrent_tasks'")

    def validate_r6_prince_judicial(self, data: dict[str, Any]) -> None:
        """R-6: Prince judicial constraints."""
        princes = [a for a in data.get("archons", []) if a.get("rank") == "Prince"]

        for prince in princes:
            name = prince.get("name", "UNKNOWN")
            for field in ["judicial_scope", "allowed_remedies", "recusal_rules"]:
                if field not in prince:
                    self.error(f"R-6: Prince {name} missing '{field}'")

    def validate_r7_marquis_advisory(self, data: dict[str, Any]) -> None:
        """R-7: Marquis advisory scope."""
        marquises = [a for a in data.get("archons", []) if a.get("rank") == "Marquis"]

        for marquis in marquises:
            name = marquis.get("name", "UNKNOWN")
            for field in ["advisory_domains", "advisory_windows", "recusal_rules"]:
                if field not in marquis:
                    self.error(f"R-7: Marquis {name} missing '{field}'")

    def validate_r8_knight_witness(self, data: dict[str, Any]) -> None:
        """R-8: Knight-Witness singular identity."""
        knights = [a for a in data.get("archons", []) if a.get("rank") == "Knight"]

        # R-8.1: Exactly 1 Knight
        if len(knights) != 1:
            self.error(f"R-8.1: Expected exactly 1 Knight, found {len(knights)}")
            return

        knight = knights[0]
        name = knight.get("name", "UNKNOWN")

        # R-8.2: branch must be "witness"
        if knight.get("branch") != "witness":
            self.error(
                f"R-8.2: Knight {name} branch must be 'witness', got '{knight.get('branch')}'"
            )

        # R-8.3: witness_violation_types
        if "witness_violation_types" not in knight:
            self.error(f"R-8.3: Knight {name} missing 'witness_violation_types'")

        # R-8.4: witness_statement_schema_version
        if "witness_statement_schema_version" not in knight:
            self.error(
                f"R-8.4: Knight {name} missing 'witness_statement_schema_version'"
            )

        # R-8.5: Hard prohibitions in governance_prohibitions
        required_prohibitions = {
            "no_propose",
            "no_debate",
            "no_define_execution",
            "no_judge",
            "no_enforce",
        }
        actual_prohibitions = set(knight.get("governance_prohibitions", []))
        missing = required_prohibitions - actual_prohibitions
        if missing:
            self.error(f"R-8.5: Knight {name} missing hard prohibitions: {missing}")

    def validate_r9_safety_language(self, data: dict[str, Any]) -> None:
        """R-9: Safety language normalization."""
        problematic_patterns = [
            r"\bsummon\b",
            r"\bconjure\b",
            r"\bdemon\b",
            r"\bdemonic\b",
            r"\bevil\b",
            r"\bwicked\b",
            r"\bhell\b",
            r"\binfernal\b",
        ]

        for archon in data.get("archons", []):
            name = archon.get("name", "UNKNOWN")
            for field in ["backstory", "system_prompt", "goal"]:
                text = archon.get(field, "").lower()
                for pattern in problematic_patterns:
                    if re.search(pattern, text):
                        self.error(
                            f"R-9: {name}.{field} contains prohibited language matching '{pattern}'"
                        )

    def validate_r10_counts(self, data: dict[str, Any]) -> None:
        """R-10: Validation rules for archon counts."""
        archons = data.get("archons", [])
        counts = {}
        for a in archons:
            rank = a.get("rank", "UNKNOWN")
            counts[rank] = counts.get(rank, 0) + 1

        # Canonical counts from Liber Infernum
        # Total: 9 + 11 + 23 + 6 + 7 + 15 + 1 = 72
        expected = {
            "King": (9, 9),  # (min, max) - exactly 9
            "President": (11, 11),  # exactly 11
            "Duke": (23, 23),  # exactly 23
            "Earl": (6, 6),  # exactly 6
            "Prince": (7, 7),  # exactly 7
            "Marquis": (15, 15),  # exactly 15
            "Knight": (1, 1),  # exactly 1 (Furcas)
        }

        for rank, (min_count, max_count) in expected.items():
            actual = counts.get(rank, 0)
            if actual < min_count or actual > max_count:
                self.error(
                    f"R-10: {rank} count {actual} not in expected range [{min_count}, {max_count}]"
                )

        # Total must be 72
        total = len(archons)
        if total != 72:
            self.error(f"R-10: Total archon count must be 72, found {total}")

    def validate_cross_references(self, data: dict[str, Any]) -> None:
        """Validate that realms/portfolios match archon assignments."""
        archons = {a["id"]: a for a in data.get("archons", []) if "id" in a}

        # Check realms reference valid Kings
        for realm in data.get("realms", []):
            archon_id = realm.get("archon_id")
            if archon_id not in archons:
                self.error(
                    f"Cross-ref: Realm {realm.get('realm_id')} references non-existent archon {archon_id}"
                )
            elif archons[archon_id].get("rank") != "King":
                self.error(
                    f"Cross-ref: Realm {realm.get('realm_id')} references non-King archon"
                )

        # Check portfolios reference valid Presidents
        for portfolio in data.get("portfolios", []):
            archon_id = portfolio.get("archon_id")
            if archon_id not in archons:
                self.error(
                    f"Cross-ref: Portfolio {portfolio.get('portfolio_id')} references non-existent archon {archon_id}"
                )
            elif archons[archon_id].get("rank") != "President":
                self.error(
                    f"Cross-ref: Portfolio {portfolio.get('portfolio_id')} references non-President archon"
                )

    def validate_governance_matrix(self, data: dict[str, Any]) -> None:
        """Validate governance_matrix structure."""
        matrix = data.get("governance_matrix", {})
        if not matrix:
            self.error("Missing governance_matrix")
            return

        required_branches = [
            "legislative",
            "executive",
            "administrative_senior",
            "administrative_strategic",
            "judicial",
            "advisory",
            "witness",
        ]

        branches = matrix.get("branches", {})
        for branch in required_branches:
            if branch not in branches:
                self.error(f"Governance matrix missing branch '{branch}'")
                continue
            branch_def = branches[branch]
            if "permissions" not in branch_def:
                self.error(f"Governance matrix branch '{branch}' missing 'permissions'")
            if "prohibitions" not in branch_def:
                self.error(
                    f"Governance matrix branch '{branch}' missing 'prohibitions'"
                )

    def report(self) -> None:
        """Print validation report."""
        if self.errors:
            print("\n=== VALIDATION ERRORS ===")
            for err in self.errors:
                print(f"  ERROR: {err}")

        if self.warnings:
            print("\n=== VALIDATION WARNINGS ===")
            for warn in self.warnings:
                print(f"  WARN: {warn}")

        if not self.errors and not self.warnings:
            print("\n=== ALL VALIDATIONS PASSED ===")
        elif not self.errors:
            print(f"\n=== PASSED with {len(self.warnings)} warnings ===")
        else:
            print(
                f"\n=== FAILED: {len(self.errors)} errors, {len(self.warnings)} warnings ==="
            )


def main() -> int:
    """Main entry point."""
    strict = "--strict" in sys.argv

    # Find archons-base.json
    json_path = Path("docs/archons-base.json")
    if not json_path.exists():
        # Try from project root
        project_root = Path(__file__).parent.parent
        json_path = project_root / "docs" / "archons-base.json"

    if not json_path.exists():
        print(f"ERROR: Cannot find archons-base.json at {json_path}")
        return 1

    print(f"Validating {json_path}")
    if strict:
        print("Running in STRICT mode")

    with open(json_path) as f:
        data = json.load(f)

    validator = ArchonValidator(strict=strict)
    valid = validator.validate(data)
    validator.report()

    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
