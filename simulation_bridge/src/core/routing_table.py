"""
Routing table for the Simulation Bridge.

Implements the DT-SB routing table described in the research paper (Table I).
Each entry maps an in-flight simulation request to its origin, enabling the
bridge to route responses back to the correct Digital Twin via the correct
north-bound protocol adapter.

Entry fields:
    PA_N        – north-bound Protocol Adapter (client-facing, e.g. "rest")
    PA_S        – south-bound Protocol Adapter (simulator-facing, e.g. "rabbitmq")
    DT          – Digital Twin identifier (client_id)
    Sim. Type   – simulation type (e.g. "matlab", "simul8")
    Request-id  – unique request identifier
    Timeout     – expiration threshold in seconds
    bridge_index – SHA-256-based anti-spoofing token

Lookup key for result routing: (request_id,)
Validation tuple from the paper: ⟨PA_S, SimType, RequestID⟩
"""

import collections
import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger()

DEFAULT_TIMEOUT_SECONDS = 60

# Defaults for configurable timeout bounds
DEFAULT_MAX_TIMEOUT = 1200   # 20 minutes
DEFAULT_MIN_TIMEOUT = 600    # 10 minutes


# ---------------------------------------------------------------------------
# Seed pool for fast bridge_index generation
# ---------------------------------------------------------------------------

class SeedPool:
    """Thread-safe pool of pre-generated random seeds.

    Seeds are consumed once and never reused.  A daemon thread refills the
    pool in the background so that message-processing threads rarely block
    on entropy generation.
    """

    def __init__(self, pool_size: int = 256) -> None:
        self._pool_size = pool_size
        self._seeds: collections.deque = collections.deque()
        self._refill_event = threading.Event()
        self._stop = False
        # Pre-fill synchronously so the pool is ready at startup
        self._generate_batch(pool_size)
        # Background daemon keeps the pool topped up
        self._thread = threading.Thread(
            target=self._refill_loop, daemon=True,
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def get(self) -> str:
        """Return a random hex seed, generating one on the spot if empty."""
        try:
            return self._seeds.popleft()
        except IndexError:
            # Pool exhausted — generate inline (rare)
            return os.urandom(32).hex()
        finally:
            # Signal refill thread if pool is running low
            if len(self._seeds) < self._pool_size // 2:
                self._refill_event.set()

    def stop(self) -> None:
        """Signal the background thread to exit (for clean shutdown)."""
        self._stop = True
        self._refill_event.set()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _generate_batch(self, count: int) -> None:
        for _ in range(count):
            self._seeds.append(os.urandom(32).hex())

    def _refill_loop(self) -> None:
        while not self._stop:
            self._refill_event.wait()
            self._refill_event.clear()
            if self._stop:
                break
            deficit = self._pool_size - len(self._seeds)
            if deficit > 0:
                self._generate_batch(deficit)


# Module-level singleton so all bridge components share a single pool
_seed_pool = SeedPool()


def generate_bridge_index(
    pa_n: str, pa_s: str, request_id: str,
) -> str:
    """Return a hex digest that binds a request to the bridge.

    ``bridge_index = sha256(pa_n || pa_s || request_id || seed)``

    The seed is a one-time random value drawn from the pre-filled
    :class:`SeedPool`, so this function never blocks on entropy.
    """
    seed = _seed_pool.get()
    data = f"{pa_n}{pa_s}{request_id}{seed}"
    return hashlib.sha256(data.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Routing entry & table
# ---------------------------------------------------------------------------

@dataclass
class RoutingEntry:
    """A single row in the DT-SB routing table."""
    pa_n: str
    pa_s: str
    dt: str
    sim_type: str
    request_id: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    created_at: float = field(default_factory=time.time)
    bridge_index: str = ''

    @property
    def is_expired(self) -> bool:
        """Check whether this entry has exceeded its timeout."""
        return (time.time() - self.created_at) > self.timeout_seconds


class RoutingTable:
    """Thread-safe dynamic routing table for in-flight simulation requests."""

    def __init__(self) -> None:
        self._entries: Dict[str, RoutingEntry] = {}
        self._seen_requests: Set[Tuple[str, str, str]] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Deduplication helpers
    # ------------------------------------------------------------------

    def has_request(
        self, request_id: str, client_id: str, simulator: str,
    ) -> bool:
        """Check whether a request with this identity triple was seen."""
        with self._lock:
            return (request_id, client_id, simulator) in self._seen_requests

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def add(self, entry: RoutingEntry,
            client_id: str = '', simulator: str = '') -> None:
        """Register a new routing entry for an outgoing request."""
        with self._lock:
            if entry.request_id in self._entries:
                logger.warning(
                    "Routing table: overwriting existing entry "
                    "for request_id=%s",
                    entry.request_id,
                )
            self._entries[entry.request_id] = entry
            if client_id and simulator:
                self._seen_requests.add(
                    (entry.request_id, client_id, simulator))
            logger.debug(
                "Routing table: added entry request_id=%s, "
                "pa_n=%s, dt=%s, sim_type=%s",
                entry.request_id, entry.pa_n, entry.dt, entry.sim_type,
            )

    def lookup(self, request_id: str) -> Optional[RoutingEntry]:
        """Look up a routing entry by request_id.

        Returns the entry if found and not expired, otherwise None.
        Expired entries are removed as a side-effect.
        """
        with self._lock:
            entry = self._entries.get(request_id)
            if entry is None:
                return None
            if entry.is_expired:
                self._remove_locked(request_id)
                logger.info(
                    "Routing table: entry expired for request_id=%s",
                    request_id,
                )
                return None
            return entry

    def remove(self, request_id: str) -> Optional[RoutingEntry]:
        """Remove and return a routing entry."""
        with self._lock:
            return self._remove_locked(request_id)

    def purge_expired(self) -> List[RoutingEntry]:
        """Remove all expired entries and return them."""
        purged: List[RoutingEntry] = []
        with self._lock:
            expired_ids = [
                rid for rid, entry in self._entries.items()
                if entry.is_expired
            ]
            for rid in expired_ids:
                entry = self._remove_locked(rid)
                if entry:
                    purged.append(entry)
                    logger.info(
                        "Routing table: purged expired entry "
                        "request_id=%s", rid,
                    )
        return purged

    # ------------------------------------------------------------------
    # Private helpers (caller must hold _lock)
    # ------------------------------------------------------------------

    def _remove_locked(self, request_id: str) -> Optional[RoutingEntry]:
        """Remove entry + dedup key while lock is held."""
        entry = self._entries.pop(request_id, None)
        if entry:
            # Remove all dedup keys that share this request_id
            self._seen_requests = {
                key for key in self._seen_requests
                if key[0] != request_id
            }
            logger.debug(
                "Routing table: removed entry request_id=%s",
                request_id,
            )
        return entry

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __contains__(self, request_id: str) -> bool:
        with self._lock:
            return request_id in self._entries
