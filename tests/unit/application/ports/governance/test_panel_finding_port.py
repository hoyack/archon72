"""Unit tests for PanelFindingPort interface.

Story: consent-gov-6-5: Panel Finding Preservation

Tests verify the port interface contract including:
- AC1: Findings recorded in append-only ledger (FR40)
- AC2: Findings cannot be deleted or modified (NFR-CONST-06)
- No delete/modify methods exist on the interface

References:
    - FR40: System can record all panel findings in append-only ledger
    - NFR-CONST-06: Panel findings cannot be deleted or modified
"""

from src.application.ports.governance.panel_finding_port import PanelFindingPort


class TestPanelFindingPortImmutabilityConstraints:
    """Test that port enforces NFR-CONST-06 by design."""

    def test_no_delete_finding_method(self) -> None:
        """Port has no delete_finding method (NFR-CONST-06).

        The absence of this method is INTENTIONAL.
        Findings cannot be deleted once recorded.
        """
        # Check the protocol doesn't define delete methods
        assert not hasattr(PanelFindingPort, "delete_finding")

    def test_no_modify_finding_method(self) -> None:
        """Port has no modify_finding method (NFR-CONST-06).

        The absence of this method is INTENTIONAL.
        Findings cannot be modified once recorded.
        """
        assert not hasattr(PanelFindingPort, "modify_finding")

    def test_no_update_finding_method(self) -> None:
        """Port has no update_finding method (NFR-CONST-06).

        The absence of this method is INTENTIONAL.
        """
        assert not hasattr(PanelFindingPort, "update_finding")

    def test_no_remove_finding_method(self) -> None:
        """Port has no remove_finding method (NFR-CONST-06).

        The absence of this method is INTENTIONAL.
        """
        assert not hasattr(PanelFindingPort, "remove_finding")

    def test_only_record_is_write_operation(self) -> None:
        """Only record_finding is a write operation.

        All other methods are read-only queries.
        """
        # The only write method should be record_finding
        write_methods = [
            attr
            for attr in dir(PanelFindingPort)
            if not attr.startswith("_")
            and callable(getattr(PanelFindingPort, attr, None))
            and attr.startswith(("record", "save", "create", "add", "insert"))
        ]
        assert write_methods == ["record_finding"]


class TestPanelFindingPortInterfaceContract:
    """Test that implementations must satisfy the port interface."""

    def test_record_finding_method_exists(self) -> None:
        """Port defines record_finding method."""
        assert hasattr(PanelFindingPort, "record_finding")

    def test_get_finding_method_exists(self) -> None:
        """Port defines get_finding method."""
        assert hasattr(PanelFindingPort, "get_finding")

    def test_get_findings_for_statement_method_exists(self) -> None:
        """Port defines statement linkage query (AC6)."""
        assert hasattr(PanelFindingPort, "get_findings_for_statement")

    def test_get_findings_by_determination_method_exists(self) -> None:
        """Port defines determination query (AC7)."""
        assert hasattr(PanelFindingPort, "get_findings_by_determination")

    def test_get_findings_by_panel_method_exists(self) -> None:
        """Port defines panel query."""
        assert hasattr(PanelFindingPort, "get_findings_by_panel")

    def test_get_findings_in_range_method_exists(self) -> None:
        """Port defines date range query (AC7)."""
        assert hasattr(PanelFindingPort, "get_findings_in_range")

    def test_get_latest_finding_method_exists(self) -> None:
        """Port defines latest finding query."""
        assert hasattr(PanelFindingPort, "get_latest_finding")

    def test_count_findings_method_exists(self) -> None:
        """Port defines count query."""
        assert hasattr(PanelFindingPort, "count_findings")


class TestPanelFindingPortRuntimeCheckable:
    """Test that port is runtime checkable."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """PanelFindingPort can be used with isinstance()."""
        # Protocol with @runtime_checkable can be used with isinstance
        # It has _is_runtime_protocol marker
        assert getattr(PanelFindingPort, "_is_runtime_protocol", False) is True
