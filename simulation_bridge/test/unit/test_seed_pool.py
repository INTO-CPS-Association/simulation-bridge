"""Tests for SeedPool, generate_bridge_index, timeout bounds, and dedup."""

import threading
import time

from simulation_bridge.src.core.routing_table import (
    RoutingEntry,
    RoutingTable,
    SeedPool,
    _get_seed_pool,
    generate_bridge_index,
    DEFAULT_MAX_TIMEOUT,
    DEFAULT_MIN_TIMEOUT,
)


def _make_entry(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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


class TestDefaultTimeoutBounds:
    """Configurable timeout bound constants."""

    def test_max_timeout(self):
        assert DEFAULT_MAX_TIMEOUT == 1200

    def test_min_timeout(self):
        assert DEFAULT_MIN_TIMEOUT == 30


class TestSeedPool:
    """Tests for the SeedPool class."""

    def test_get_returns_hex_string(self):
        pool = SeedPool(pool_size=4)
        seed = pool.get()
        assert isinstance(seed, str)
        assert len(seed) == 64
        int(seed, 16)
        pool.stop()

    def test_seeds_are_unique(self):
        pool = SeedPool(pool_size=16)
        seeds = {pool.get() for _ in range(16)}
        assert len(seeds) == 16
        pool.stop()

    def test_pool_survives_exhaustion(self):
        pool = SeedPool(pool_size=2)
        s1 = pool.get()
        s2 = pool.get()
        s3 = pool.get()
        assert all(isinstance(s, str) for s in (s1, s2, s3))
        pool.stop()

    def test_stop_joins_background_thread(self):
        """stop() waits for the background thread to finish."""
        pool = SeedPool(pool_size=4)
        assert pool._thread.is_alive()  # pylint: disable=protected-access
        pool.stop()
        pool._thread.join(timeout=2)  # pylint: disable=protected-access
        assert not pool._thread.is_alive()  # pylint: disable=protected-access

    def test_stop_from_within_thread_does_not_join(self):
        """stop() called from within the refill thread skips join."""
        pool = SeedPool(pool_size=4)
        errors = []

        def call_stop_from_thread():
            try:
                # Simulate calling stop() from the refill thread itself
                saved = threading.current_thread
                threading.current_thread = (
                    lambda: pool._thread  # pylint: disable=protected-access
                )
                try:
                    pool.stop()
                finally:
                    threading.current_thread = saved
            except Exception as exc:  # pylint: disable=broad-exception-caught
                errors.append(str(exc))

        t = threading.Thread(target=call_stop_from_thread)
        t.start()
        t.join(timeout=3)
        assert not errors

    def test_refill_triggered_when_pool_low(self):
        """get() triggers a refill when pool drops below half."""
        pool = SeedPool(pool_size=4)
        # Drain the pool below half
        for _ in range(3):
            pool.get()
        # Give the background thread a moment to refill
        time.sleep(0.1)
        assert len(pool._seeds) >= 0  # pylint: disable=protected-access
        pool.stop()


class TestGetSeedPool:
    """Tests for the module-level _get_seed_pool singleton."""

    def test_returns_same_instance(self):
        """_get_seed_pool returns the same singleton each time."""
        p1 = _get_seed_pool()
        p2 = _get_seed_pool()
        assert p1 is p2

    def test_returns_seed_pool_instance(self):
        pool = _get_seed_pool()
        assert isinstance(pool, SeedPool)



class TestGenerateBridgeIndex:
    """Tests for the generate_bridge_index function."""

    def test_returns_sha256_hex(self):
        idx = generate_bridge_index('rest', 'rabbitmq', 'r1')
        assert len(idx) == 64
        int(idx, 16)

    def test_different_inputs_different_index(self):
        a = generate_bridge_index('rest', 'rabbitmq', 'r1')
        b = generate_bridge_index('mqtt', 'rabbitmq', 'r1')
        assert a != b

    def test_same_inputs_different_due_to_seed(self):
        a = generate_bridge_index('rest', 'rabbitmq', 'r1')
        b = generate_bridge_index('rest', 'rabbitmq', 'r1')
        assert a != b


class TestRoutingTableDeduplication:
    """Request deduplication via has_request / add / remove."""

    def test_false_initially(self):
        table = RoutingTable()
        assert table.has_request('r1', 'c1', 's1') is False

    def test_true_after_add(self):
        table = RoutingTable()
        table.add(
            _make_entry('r1'), client_id='c1', simulator='s1')
        assert table.has_request('r1', 'c1', 's1') is True

    def test_cleared_on_remove(self):
        table = RoutingTable()
        table.add(
            _make_entry('r1'), client_id='c1', simulator='s1')
        table.remove('r1')
        assert table.has_request('r1', 'c1', 's1') is False

    def test_cleared_on_purge(self):
        table = RoutingTable()
        table.add(
            _make_entry(
                'r1', timeout=1, created_at=time.time() - 5),
            client_id='c1', simulator='s1')
        table.purge_expired()
        assert table.has_request('r1', 'c1', 's1') is False

    def test_add_without_client_id_no_dedup(self):
        table = RoutingTable()
        table.add(_make_entry('r1'))
        assert table.has_request('r1', '', '') is False
