"""Capability Uplift Sprint helpers — see ``docs/streams/STREAM-UPLIFT-DESIGN.md``.

This package houses cross-cutting helpers for Sprint #1 to #8 that don't
fit cleanly into an existing module:

- ``threat_metrics``: Prometheus counters shared by trigger / memory scan
  paths.
- ``threat_scan``: per-resource scan helpers (recursive ``str`` walker
  with size cap; audit emit wrappers).
"""
