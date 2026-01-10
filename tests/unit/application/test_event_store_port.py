"""Unit tests for EventStorePort methods (Story 1.5, Task 2; Story 4.3, Task 2).

Tests sequence continuity validation for observer verification.
Tests filtered query method signatures (FR46).

Constitutional Constraints Tested:
- FR7: Sequence numbers must be monotonically increasing and unique
- FR46: Query interface supports date range and event type filtering
- AC2: Unique sequential numbers with no gaps (except ceremonies)
- AC3: Sequence as authoritative order
"""


from src.application.ports.event_store import validate_sequence_continuity


class TestValidateSequenceContinuity:
    """Tests for validate_sequence_continuity helper."""

    def test_empty_sequence_list_is_continuous(self) -> None:
        """Empty sequence list is considered continuous."""
        is_continuous, missing = validate_sequence_continuity(sequences=[])
        assert is_continuous is True
        assert missing == []

    def test_single_sequence_is_continuous(self) -> None:
        """Single sequence is continuous."""
        is_continuous, missing = validate_sequence_continuity(sequences=[1])
        assert is_continuous is True
        assert missing == []

    def test_continuous_sequence_no_gaps(self) -> None:
        """Continuous sequence with no gaps."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[1, 2, 3, 4, 5]
        )
        assert is_continuous is True
        assert missing == []

    def test_continuous_sequence_starting_higher(self) -> None:
        """Continuous sequence starting from a number other than 1."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[10, 11, 12, 13]
        )
        assert is_continuous is True
        assert missing == []

    def test_gap_in_sequence_detected(self) -> None:
        """Detects gap in sequence."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[1, 2, 4, 5]  # Missing 3
        )
        assert is_continuous is False
        assert missing == [3]

    def test_multiple_gaps_detected(self) -> None:
        """Detects multiple gaps in sequence."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[1, 2, 5, 8]  # Missing 3, 4, 6, 7
        )
        assert is_continuous is False
        assert sorted(missing) == [3, 4, 6, 7]

    def test_large_gap_detected(self) -> None:
        """Detects large gap in sequence."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[1, 100]  # Missing 2-99
        )
        assert is_continuous is False
        assert len(missing) == 98  # 2 through 99

    def test_unsorted_input_handled(self) -> None:
        """Handles unsorted input sequences."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[3, 1, 2, 5, 4]  # Unsorted but continuous
        )
        assert is_continuous is True
        assert missing == []

    def test_unsorted_with_gap(self) -> None:
        """Handles unsorted input with gap."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[5, 1, 3, 2]  # Missing 4, unsorted
        )
        assert is_continuous is False
        assert missing == [4]

    def test_duplicate_sequences_still_detects_gaps(self) -> None:
        """Duplicates don't affect gap detection."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[1, 2, 2, 4, 4]  # Missing 3
        )
        assert is_continuous is False
        assert missing == [3]

    def test_with_expected_start(self) -> None:
        """Detects missing sequences from expected start."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[3, 4, 5],
            expected_start=1,
        )
        assert is_continuous is False
        assert sorted(missing) == [1, 2]

    def test_with_expected_end(self) -> None:
        """Detects missing sequences up to expected end."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[1, 2, 3],
            expected_end=5,
        )
        assert is_continuous is False
        assert sorted(missing) == [4, 5]

    def test_with_expected_start_and_end(self) -> None:
        """Detects gaps with both start and end constraints."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[3, 4, 6],
            expected_start=1,
            expected_end=8,
        )
        assert is_continuous is False
        assert sorted(missing) == [1, 2, 5, 7, 8]

    def test_exact_range_is_continuous(self) -> None:
        """Sequence matching expected range is continuous."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[1, 2, 3, 4, 5],
            expected_start=1,
            expected_end=5,
        )
        assert is_continuous is True
        assert missing == []

    def test_negative_sequences_handled(self) -> None:
        """Negative sequences handled correctly (edge case)."""
        # Note: Real sequences should always be positive, but function should handle
        is_continuous, missing = validate_sequence_continuity(
            sequences=[-2, -1, 0, 1, 2]
        )
        assert is_continuous is True
        assert missing == []

    def test_very_large_sequences(self) -> None:
        """Handles very large sequence numbers."""
        is_continuous, missing = validate_sequence_continuity(
            sequences=[1000000, 1000001, 1000002]
        )
        assert is_continuous is True
        assert missing == []


# =============================================================================
# Tests for Orphaning Extension (Story 3.10, Task 9)
# =============================================================================

import inspect
from abc import ABC

from src.application.ports.event_store import EventStorePort


class TestEventStorePortOrphaningExtension:
    """Tests for EventStorePort orphaning methods (Story 3.10, Task 9).

    Constitutional Constraints:
    - FR143: Rollback to checkpoint for infrastructure recovery
    - PREVENT_DELETE: Events are never deleted, only marked orphaned
    """

    def test_mark_events_orphaned_method_signature(self) -> None:
        """mark_events_orphaned should exist with correct parameters."""
        method = getattr(EventStorePort, "mark_events_orphaned", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert "start_sequence" in params
        assert "end_sequence" in params

    def test_get_head_sequence_method_signature(self) -> None:
        """get_head_sequence should exist with correct signature."""
        method = getattr(EventStorePort, "get_head_sequence", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        # Should have minimal parameters (just self)
        assert len(params) == 1

    def test_set_head_sequence_method_signature(self) -> None:
        """set_head_sequence should exist with sequence parameter."""
        method = getattr(EventStorePort, "set_head_sequence", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert "sequence" in params

    def test_query_with_include_orphaned_flag(self) -> None:
        """get_events_by_sequence_range_with_orphaned should exist."""
        method = getattr(EventStorePort, "get_events_by_sequence_range_with_orphaned", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert "start" in params
        assert "end" in params
        assert "include_orphaned" in params


# =============================================================================
# Tests for Filtered Query Methods (Story 4.3, Task 2 - FR46)
# =============================================================================


class TestEventStorePortFilteredQueries:
    """Tests for EventStorePort filtered query methods (Story 4.3, Task 2).

    Constitutional Constraints:
    - FR46: Query interface SHALL support date range and event type filtering
    """

    def test_port_defines_get_events_filtered(self) -> None:
        """get_events_filtered method should exist with correct parameters."""
        method = getattr(EventStorePort, "get_events_filtered", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Required parameters
        assert "self" in params
        assert "limit" in params
        assert "offset" in params
        assert "start_date" in params
        assert "end_date" in params
        assert "event_types" in params

    def test_port_defines_count_events_filtered(self) -> None:
        """count_events_filtered method should exist with correct parameters."""
        method = getattr(EventStorePort, "count_events_filtered", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Required parameters
        assert "self" in params
        assert "start_date" in params
        assert "end_date" in params
        assert "event_types" in params

    def test_get_events_filtered_is_abstract(self) -> None:
        """get_events_filtered should be an abstract method."""
        method = getattr(EventStorePort, "get_events_filtered", None)
        assert method is not None
        # Check it's decorated with abstractmethod
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_count_events_filtered_is_abstract(self) -> None:
        """count_events_filtered should be an abstract method."""
        method = getattr(EventStorePort, "count_events_filtered", None)
        assert method is not None
        # Check it's decorated with abstractmethod
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_get_events_filtered_default_parameters(self) -> None:
        """get_events_filtered should have appropriate default values."""
        sig = inspect.signature(EventStorePort.get_events_filtered)
        params = sig.parameters

        # Check defaults
        assert params["limit"].default == 100
        assert params["offset"].default == 0
        assert params["start_date"].default is None
        assert params["end_date"].default is None
        assert params["event_types"].default is None

    def test_count_events_filtered_default_parameters(self) -> None:
        """count_events_filtered should have appropriate default values."""
        sig = inspect.signature(EventStorePort.count_events_filtered)
        params = sig.parameters

        # All filter params should default to None
        assert params["start_date"].default is None
        assert params["end_date"].default is None
        assert params["event_types"].default is None


# =============================================================================
# Tests for Historical Query Methods (Story 4.5, Task 4 - FR88, FR89)
# =============================================================================


class TestEventStorePortHistoricalQueries:
    """Tests for EventStorePort historical query methods (Story 4.5, Task 4).

    Constitutional Constraints:
    - FR88: Query for state as of any sequence number or timestamp
    - FR89: Historical queries return hash chain proof to current head
    """

    def test_port_defines_get_events_up_to_sequence(self) -> None:
        """get_events_up_to_sequence method should exist with correct parameters."""
        method = getattr(EventStorePort, "get_events_up_to_sequence", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Required parameters
        assert "self" in params
        assert "max_sequence" in params
        assert "limit" in params
        assert "offset" in params

    def test_get_events_up_to_sequence_is_abstract(self) -> None:
        """get_events_up_to_sequence should be an abstract method."""
        method = getattr(EventStorePort, "get_events_up_to_sequence", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_get_events_up_to_sequence_default_parameters(self) -> None:
        """get_events_up_to_sequence should have appropriate default values."""
        sig = inspect.signature(EventStorePort.get_events_up_to_sequence)
        params = sig.parameters

        # Check defaults
        assert params["limit"].default == 100
        assert params["offset"].default == 0

    def test_port_defines_count_events_up_to_sequence(self) -> None:
        """count_events_up_to_sequence method should exist."""
        method = getattr(EventStorePort, "count_events_up_to_sequence", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "max_sequence" in params

    def test_count_events_up_to_sequence_is_abstract(self) -> None:
        """count_events_up_to_sequence should be an abstract method."""
        method = getattr(EventStorePort, "count_events_up_to_sequence", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_port_defines_find_sequence_for_timestamp(self) -> None:
        """find_sequence_for_timestamp method should exist."""
        method = getattr(EventStorePort, "find_sequence_for_timestamp", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "timestamp" in params

    def test_find_sequence_for_timestamp_is_abstract(self) -> None:
        """find_sequence_for_timestamp should be an abstract method."""
        method = getattr(EventStorePort, "find_sequence_for_timestamp", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False) is True


# =============================================================================
# Tests for Streaming Export Methods (Story 4.7, Task 4 - FR139)
# =============================================================================


class TestEventStorePortStreamingExport:
    """Tests for EventStorePort streaming methods (Story 4.7, Task 4).

    Constitutional Constraints:
    - FR139: Export SHALL support structured audit format
    - Export must support streaming for large datasets
    """

    def test_port_defines_stream_events(self) -> None:
        """stream_events method should exist with correct parameters."""
        method = getattr(EventStorePort, "stream_events", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Required parameters
        assert "self" in params
        assert "start_sequence" in params
        assert "end_sequence" in params
        assert "start_date" in params
        assert "end_date" in params
        assert "event_types" in params
        assert "batch_size" in params

    def test_stream_events_is_abstract(self) -> None:
        """stream_events should be an abstract method."""
        method = getattr(EventStorePort, "stream_events", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_stream_events_default_parameters(self) -> None:
        """stream_events should have appropriate default values."""
        sig = inspect.signature(EventStorePort.stream_events)
        params = sig.parameters

        # All filter params should default to None
        assert params["start_sequence"].default is None
        assert params["end_sequence"].default is None
        assert params["start_date"].default is None
        assert params["end_date"].default is None
        assert params["event_types"].default is None
        assert params["batch_size"].default == 100

    def test_port_defines_count_events_in_range(self) -> None:
        """count_events_in_range method should exist with correct parameters."""
        method = getattr(EventStorePort, "count_events_in_range", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Required parameters
        assert "self" in params
        assert "start_sequence" in params
        assert "end_sequence" in params

    def test_count_events_in_range_is_abstract(self) -> None:
        """count_events_in_range should be an abstract method."""
        method = getattr(EventStorePort, "count_events_in_range", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False) is True
