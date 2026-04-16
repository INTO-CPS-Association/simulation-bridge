"""
Test suite for routing_table.py.

Covers RoutingEntry, RoutingTable add/lookup/remove/purge_expired,
thread-safety, and edge cases.
"""

import time
import threading

from simulation_bridge.src.core.routing_table import (
    RoutingEntry,
    RoutingTable,
    DEFAULT_TIMEOUT_SECONDS,
)

# pylint: disable=redefined-outer-name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        request_id="req-1", pa_n="rest", pa_s="rabbitmq",
        dt="DT_1", sim_type="matlab", timeout=60, created_at=None):
    """Create a RoutingEntry with sensible defaults."""
    entry = RoutingEntry(
        pa_n=pa_n,
        pa_s=pa_s,
        dt=dt,
        sim_type=sim_type,
        request_id=request_id,
        timeout_seconds=timeout,
    )
    if created_at is not None:
        entry.created_at = created_at
    return entry


# ---------------------------------------------------------------------------
# RoutingEntry
# ---------------------------------------------------------------------------

class TestRoutingEntry:
    """Tests for the RoutingEntry dataclass."""

    def test_default_timeout(self):
        """Default timeout equals module-level constant."""
        entry = _make_entry()
        assert entry.timeout_seconds == 60

    def test_is_expired_false_when_fresh(self):
        """A freshly created entry is not expired."""
        entry = _make_entry(timeout=10)
        assert entry.is_expired is False

    def test_is_expired_true_when_old(self):
        """An entry created in the past beyond its timeout is expired."""
        entry = _make_entry(timeout=1, created_at=time.time() - 2)
        assert entry.is_expired is True

    def test_created_at_auto_populated(self):
        """created_at is automatically set to approximately now."""
        before = time.time()
        entry = _make_entry()
        after = time.time()
        assert before <= entry.created_at <= after


# ---------------------------------------------------------------------------
# RoutingTable — basic operations
# ---------------------------------------------------------------------------

class TestRoutingTableBasic:
    """Tests for basic RoutingTable add / lookup / remove."""

    def test_add_and_lookup(self):
        """An added entry is retrievable via lookup."""
        table = RoutingTable()
        entry = _make_entry()
        table.add(entry)
        result = table.lookup("req-1")
        assert result is entry

    def test_lookup_missing_returns_none(self):
        """Looking up a non-existent request_id returns None."""
        table = RoutingTable()
        assert table.lookup("nonexistent") is None

    def test_remove_returns_entry(self):
        """remove() returns the entry and clears it from the table."""
        table = RoutingTable()
        entry = _make_entry()
        table.add(entry)
        removed = table.remove("req-1")
        assert removed is entry
        assert table.lookup("req-1") is None

    def test_remove_missing_returns_none(self):
        """remove() on a non-existent key returns None."""
        table = RoutingTable()
        assert table.remove("nope") is None

    def test_len(self):
        """__len__ reports the number of active entries."""
        table = RoutingTable()
        assert len(table) == 0
        table.add(_make_entry("a"))
        table.add(_make_entry("b"))
        assert len(table) == 2

    def test_contains(self):
        """__contains__ checks membership by request_id."""
        table = RoutingTable()
        table.add(_make_entry("x"))
        assert "x" in table
        assert "y" not in table


# ---------------------------------------------------------------------------
# RoutingTable — overwrite, expiry, purge
# ---------------------------------------------------------------------------

class TestRoutingTableExpiry:
    """Tests for timeout and purge behaviour."""

    def test_add_overwrites_existing(self):
        """Adding an entry with the same request_id overwrites the old one."""
        table = RoutingTable()
        table.add(_make_entry("r1", pa_n="mqtt"))
        table.add(_make_entry("r1", pa_n="rest"))
        entry = table.lookup("r1")
        assert entry.pa_n == "rest"
        assert len(table) == 1

    def test_lookup_removes_expired_entry(self):
        """lookup() returns None and removes an expired entry."""
        table = RoutingTable()
        table.add(_make_entry("r1", timeout=1, created_at=time.time() - 2))
        assert table.lookup("r1") is None
        assert len(table) == 0

    def test_purge_expired_removes_old_entries(self):
        """purge_expired() removes entries past their timeout."""
        table = RoutingTable()
        table.add(_make_entry("old", timeout=1, created_at=time.time() - 5))
        table.add(_make_entry("fresh", timeout=300))
        purged = table.purge_expired()
        assert len(purged) == 1
        assert purged[0].request_id == "old"
        assert len(table) == 1
        assert "fresh" in table

    def test_purge_expired_empty_table(self):
        """purge_expired() on an empty table returns an empty list."""
        table = RoutingTable()
        assert not table.purge_expired()


# ---------------------------------------------------------------------------
# RoutingTable — thread safety
# ---------------------------------------------------------------------------

class TestRoutingTableThreadSafety:
    """Verify that concurrent add/lookup/remove do not corrupt state."""

    def test_concurrent_add_and_lookup(self):
        """Many threads can add and look up entries safely."""
        table = RoutingTable()
        n_threads = 20
        entries_per_thread = 50
        errors = []

        def worker(tid):
            try:
                for i in range(entries_per_thread):
                    rid = f"t{tid}-{i}"
                    table.add(_make_entry(rid, timeout=300))
                    result = table.lookup(rid)
                    if result is None or result.request_id != rid:
                        errors.append(f"lookup failed for {rid}")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(t,))
                   for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors: {errors}"
        assert len(table) == n_threads * entries_per_thread

    def test_concurrent_add_and_remove(self):
        """Concurrent add + remove cycles leave a consistent table."""
        table = RoutingTable()
        n_threads = 10
        iterations = 100
        errors = []

        def worker(tid):
            try:
                for i in range(iterations):
                    rid = f"t{tid}-{i}"
                    table.add(_make_entry(rid, timeout=300))
                    table.remove(rid)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(t,))
                   for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(table) == 0


# ---------------------------------------------------------------------------
# RoutingTable — default timeout constant
# ---------------------------------------------------------------------------

class TestDefaultTimeout:
    """Verify the module-level DEFAULT_TIMEOUT_SECONDS constant."""

    def test_value(self):
        assert DEFAULT_TIMEOUT_SECONDS == 60
