"""Shared provider-layer metrics — Stream HX-13."""

from __future__ import annotations

from helix_agent.common.observability import helix_counter

#: Stream HX-13 (Mini-ADR HX-J4) — vendor-native tool-disclosure tier
#: rejected by the API; the provider instance fell back to the HX-12
#: application tier for its remaining lifetime.
disclosure_fallback_total = helix_counter(
    "helix_llm_tool_disclosure_fallback_total",
    "Vendor-native tool-disclosure tier rejections (fell back to the HX-12 tier).",
    ("provider",),
)
