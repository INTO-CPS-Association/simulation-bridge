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

Lookup key for result routing: (request_id,)
Validation tuple from the paper: ⟨PA_S, SimType, RequestID⟩
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger()

DEFAULT_TIMEOUT_SECONDS = 60


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

    @property
    def is_expired(self) -> bool:
        """Check whether this entry has exceeded its timeout."""
        return (time.time() - self.created_at) > self.timeout_seconds


class RoutingTable:
    """Thread-safe dynamic routing table for in-flight simulation requests."""

    def __init__(self) -> None:
        self._entries: Dict[str, RoutingEntry] = {}
        self._lock = threading.Lock()

    def add(self, entry: RoutingEntry) -> None:
        """Register a new routing entry for an outgoing request."""
        with self._lock:
            if entry.request_id in self._entries:
                logger.warning(
                    "Routing table: overwriting existing entry for request_id=%s",
                    entry.request_id,
                )
            self._entries[entry.request_id] = entry
            logger.debug(
                "Routing table: added entry request_id=%s, pa_n=%s, dt=%s, sim_type=%s",
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
                del self._entries[request_id]
                logger.info(
                    "Routing table: entry expired for request_id=%s",
                    request_id,
                )
                return None
            return entry

    def remove(self, request_id: str) -> Optional[RoutingEntry]:
        """Remove and return a routing entry (e.g. after final result delivery)."""
        with self._lock:
            entry = self._entries.pop(request_id, None)
            if entry:
                logger.debug(
                    "Routing table: removed entry request_id=%s",
                    request_id,
                )
            return entry

    def purge_expired(self) -> List[RoutingEntry]:
        """Remove all expired entries and return them."""
        purged: List[RoutingEntry] = []
        with self._lock:
            expired_ids = [
                rid for rid, entry in self._entries.items()
                if entry.is_expired
            ]
            for rid in expired_ids:
                purged.append(self._entries.pop(rid))
                logger.info(
                    "Routing table: purged expired entry request_id=%s", rid,
                )
        return purged

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __contains__(self, request_id: str) -> bool:
        with self._lock:
            return request_id in self._entries
