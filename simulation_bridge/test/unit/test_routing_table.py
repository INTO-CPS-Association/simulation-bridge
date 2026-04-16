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
    SeedPool,
    generate_bridge_index,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_MAX_TIMEOUT,
    DEFAULT_MIN_TIMEOUT,
)

# pylint: disable=redefined-outer-name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        request_id="req-1", pa_n="rest", pa_s="rabbitmq",
        dt="DT_1", sim_type="matlab", timeout=60,
        created_at=None, bridge_index=''):
    """Create a RoutingEntry with sensible defaults."""
    entry = RoutingEntry(
        pa_n=pa_n,
        pa_s=pa_s,
        dt=dt,
        sim_type=sim_type,
        request_id=request_id,
        timeout_seconds=timeout,
        bridge_index=bridge_index,
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


class TestDefaultTimeoutBounds:
    """Verify the configurable timeout bound constants."""

    def test_max_timeout(self):
        assert DEFAULT_MAX_TIMEOUT == 1200

    def test_min_timeout(self):
        assert DEFAULT_MIN_TIMEOUT == 600


# ---------------------------------------------------------------------------
# SeedPool
# ---------------------------------------------------------------------------

class TestSeedPool:
    """Tests for the SeedPool class."""

    def test_get_returns_hex_string(self):
        """Each seed is a 64-character hex string."""
        pool = SeedPool(pool_size=4)
        seed = pool.get()
        assert isinstance(seed, str)
        assert len(seed) == 64
        int(seed, 16)  # must be valid hex
        pool.stop()

    def test_seeds_are_unique(self):
        """Successive seeds are distinct."""
        pool = SeedPool(pool_size=16)
        seeds = {pool.get() for _ in range(16)}
        assert len(seeds) == 16
        pool.stop()

    def test_pool_survives_exhaustion(self):
        """Pool generates inline seeds when exhausted."""
        pool = SeedPool(pool_size=2)
        s1 = pool.get()
        s2 = pool.get()
        s3 = pool.get()  # pool empty — inline generation
        assert all(isinstance(s, str) for s in (s1, s2, s3))
        pool.stop()


# ---------------------------------------------------------------------------
# generate_bridge_index
# ---------------------------------------------------------------------------

class TestGenerateBridgeIndex:
    """Tests for the generate_bridge_index function."""

    def test_returns_sha256_hex(self):
        """Returns a 64-character hex digest."""
        idx = generate_bridge_index('rest', 'rabbitmq', 'r1')
        assert len(idx) == 64
        int(idx, 16)

    def test_different_inputs_different_index(self):
        """Different input tuples produce different bridge_index values."""
        a = generate_bridge_index('rest', 'rabbitmq', 'r1')
        b = generate_bridge_index('mqtt', 'rabbitmq', 'r1')
        assert a != b

    def test_same_inputs_different_due_to_seed(self):
        """Same inputs produce different bridge_index because seed differs."""
        a = generate_bridge_index('rest', 'rabbitmq', 'r1')
        b = generate_bridge_index('rest', 'rabbitmq', 'r1')
        assert a != b


# ---------------------------------------------------------------------------
# RoutingTable — deduplication
# ---------------------------------------------------------------------------

class TestRoutingTableDeduplication:
    """Tests for request deduplication via has_request / add / remove."""

    def test_has_request_returns_false_initially(self):
        table = RoutingTable()
        assert table.has_request('r1', 'c1', 's1') is False

    def test_has_request_returns_true_after_add(self):
        table = RoutingTable()
        table.add(_make_entry('r1'), client_id='c1', simulator='s1')
        assert table.has_request('r1', 'c1', 's1') is True

    def test_dedup_key_cleared_on_remove(self):
        table = RoutingTable()
        table.add(_make_entry('r1'), client_id='c1', simulator='s1')
        table.remove('r1')
        assert table.has_request('r1', 'c1', 's1') is False

    def test_dedup_key_cleared_on_purge(self):
        table = RoutingTable()
        table.add(
            _make_entry('r1', timeout=1, created_at=time.time() - 5),
            client_id='c1', simulator='s1')
        table.purge_expired()
        assert table.has_request('r1', 'c1', 's1') is False

    def test_add_without_client_id_no_dedup(self):
        """add() without client_id/simulator does not register dedup key."""
        table = RoutingTable()
        table.add(_make_entry('r1'))
        assert table.has_request('r1', '', '') is False
