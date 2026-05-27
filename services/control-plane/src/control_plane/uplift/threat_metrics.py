"""Prometheus counters for the Capability Uplift threat scanners.

See ``docs/streams/STREAM-UPLIFT-DESIGN.md`` § 1.3 + § 2.6.

Counters are intentionally low-cardinality:

- ``scope`` ∈ ``{all, context, strict}`` (3 values)
- ``result`` ∈ ``{clean, blocked, warned}`` (3 values)
- ``phase`` ∈ ``{create, fire}`` (2 values, plus ``memory_write`` /
  ``memory_recall`` reserved for Sprint #2)
- ``pattern_id`` is bounded by the pattern registry (currently ~30 IDs);
  if the registry grows past 100 we'll move to a histogram-of-counts
  per ``category`` instead.
"""

from __future__ import annotations

from collections.abc import Iterable

from helix_agent.common.observability import helix_counter
from helix_agent.common.threat_patterns import ThreatFinding

_scan_total = helix_counter(
    "helix_uplift_threat_scan_total",
    "Number of threat-scan invocations, partitioned by scope and result.",
    label_names=("scope", "result"),
)

_pattern_hit_total = helix_counter(
    "helix_uplift_threat_pattern_hit_total",
    "Per-pattern hit count from threat scans (used for tuning).",
    label_names=("pattern_id", "scope"),
)

_triggers_blocked_total = helix_counter(
    "helix_uplift_triggers_blocked_total",
    "Triggers refused by the prompt-injection scanner.",
    label_names=("phase",),
)


def record_threat_scan(*, scope: str, result: str) -> None:
    """Bump ``helix_uplift_threat_scan_total``."""
    _scan_total.labels(scope=scope, result=result).inc()


def record_threat_pattern_hits(findings: Iterable[ThreatFinding], *, scope: str) -> None:
    """Bump ``helix_uplift_threat_pattern_hit_total`` once per finding."""
    for f in findings:
        _pattern_hit_total.labels(pattern_id=f.pattern_id, scope=scope).inc()


def record_trigger_blocked(*, phase: str) -> None:
    """Bump ``helix_uplift_triggers_blocked_total{phase}``."""
    _triggers_blocked_total.labels(phase=phase).inc()


__all__ = [
    "record_threat_pattern_hits",
    "record_threat_scan",
    "record_trigger_blocked",
]
