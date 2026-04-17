"""Tests for SeedPool, generate_bridge_index, timeout bounds, and dedup."""

import time

from simulation_bridge.src.core.routing_table import (
    RoutingEntry,
    RoutingTable,
    SeedPool,
    generate_bridge_index,
    DEFAULT_MAX_TIMEOUT,
    DEFAULT_MIN_TIMEOUT,
)


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
