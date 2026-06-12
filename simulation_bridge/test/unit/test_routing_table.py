"""Tests for RoutingEntry and RoutingTable core operations."""

import time
import threading

from simulation_bridge.src.core.routing_table import (
    RoutingEntry,
    RoutingTable,
    DEFAULT_TIMEOUT_SECONDS,
)

# pylint: disable=redefined-outer-name


def _make_entry(
        request_id="req-1", pa_n="rest", pa_s="rabbitmq",
        dt="DT_1", sim_type="matlab", timeout=60,
        created_at=None, bridge_index=''):
    """Create a RoutingEntry with sensible defaults."""
    entry = RoutingEntry(
        pa_n=pa_n, pa_s=pa_s, dt=dt, sim_type=sim_type,
        request_id=request_id, timeout_seconds=timeout,
        bridge_index=bridge_index)
    if created_at is not None:
        entry.created_at = created_at
    return entry


class TestRoutingEntry:
    """Tests for the RoutingEntry dataclass."""

    def test_default_timeout(self):
        entry = _make_entry()
        assert entry.timeout_seconds == 60

    def test_is_expired_false_when_fresh(self):
        entry = _make_entry(timeout=10)
        assert entry.is_expired is False

    def test_is_expired_true_when_old(self):
        entry = _make_entry(
            timeout=1, created_at=time.time() - 2)
        assert entry.is_expired is True

    def test_created_at_auto_populated(self):
        before = time.time()
        entry = _make_entry()
        after = time.time()
        assert before <= entry.created_at <= after


class TestRoutingTableBasic:
    """Tests for add / lookup / remove."""

    def test_add_and_lookup(self):
        table = RoutingTable()
        entry = _make_entry()
        table.add(entry)
        assert table.lookup("req-1") is entry

    def test_lookup_missing_returns_none(self):
        table = RoutingTable()
        assert table.lookup("nonexistent") is None

    def test_remove_returns_entry(self):
        table = RoutingTable()
        entry = _make_entry()
        table.add(entry)
        removed = table.remove("req-1")
        assert removed is entry
        assert table.lookup("req-1") is None

    def test_remove_missing_returns_none(self):
        table = RoutingTable()
        assert table.remove("nope") is None

    def test_len(self):
        table = RoutingTable()
        assert len(table) == 0
        table.add(_make_entry("a"))
        table.add(_make_entry("b"))
        assert len(table) == 2

    def test_contains(self):
        table = RoutingTable()
        table.add(_make_entry("x"))
        assert "x" in table
        assert "y" not in table


class TestRoutingTableExpiry:
    """Tests for timeout and purge behaviour."""

    def test_add_overwrites_existing(self):
        table = RoutingTable()
        table.add(_make_entry("r1", pa_n="mqtt"))
        table.add(_make_entry("r1", pa_n="rest"))
        entry = table.lookup("r1")
        assert entry.pa_n == "rest"
        assert len(table) == 1

    def test_lookup_removes_expired_entry(self):
        table = RoutingTable()
        table.add(_make_entry(
            "r1", timeout=1, created_at=time.time() - 2))
        assert table.lookup("r1") is None
        assert len(table) == 0

    def test_purge_expired_removes_old_entries(self):
        table = RoutingTable()
        table.add(_make_entry(
            "old", timeout=1, created_at=time.time() - 5))
        table.add(_make_entry("fresh", timeout=300))
        purged = table.purge_expired()
        assert len(purged) == 1
        assert purged[0].request_id == "old"
        assert len(table) == 1
        assert "fresh" in table

    def test_purge_expired_empty_table(self):
        table = RoutingTable()
        assert not table.purge_expired()


class TestRoutingTableThreadSafety:
    """Concurrent add/lookup/remove do not corrupt state."""

    def test_concurrent_add_and_lookup(self):
        table = RoutingTable()
        n_threads, per = 20, 50
        errors = []

        def worker(tid):
            try:
                for i in range(per):
                    rid = f"t{tid}-{i}"
                    table.add(_make_entry(rid, timeout=300))
                    result = table.lookup(rid)
                    if result is None or result.request_id != rid:
                        errors.append(f"fail {rid}")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                errors.append(str(exc))

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(table) == n_threads * per

    def test_concurrent_add_and_remove(self):
        table = RoutingTable()
        n_threads, iters = 10, 100
        errors = []

        def worker(tid):
            try:
                for i in range(iters):
                    rid = f"t{tid}-{i}"
                    table.add(_make_entry(rid, timeout=300))
                    table.remove(rid)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                errors.append(str(exc))

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(table) == 0


class TestDefaultTimeout:
    """Module-level DEFAULT_TIMEOUT_SECONDS constant."""

    def test_value(self):
        assert DEFAULT_TIMEOUT_SECONDS == 60
