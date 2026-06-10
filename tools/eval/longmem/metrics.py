"""Retrieval metrics — pure functions, Stream CM-N5 P0 tier.

All three operate on an *ordered* list of retrieved ids against a set of
relevant ids (binary relevance). Recall follows the same convention as
``memory_recall.recall_at_k`` (|relevant ∩ top-k| / |relevant|); NDCG@k
uses binary gains; MRR rewards ranking the first relevant id high.
Empty-relevance inputs score 1.0 for recall/NDCG (a no-op case, not a
failure) and 0.0 for MRR-style rank metrics is avoided the same way.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def recall_at_k(retrieved: Sequence[str], relevant: frozenset[str] | set[str], k: int) -> float:
    if not relevant:
        return 1.0
    if k <= 0:
        return 0.0
    top = set(retrieved[:k])
    return sum(1 for r in relevant if r in top) / len(relevant)


def ndcg_at_k(retrieved: Sequence[str], relevant: frozenset[str] | set[str], k: int) -> float:
    if not relevant:
        return 1.0
    if k <= 0:
        return 0.0
    dcg = sum(
        1.0 / math.log2(rank + 2.0) for rank, rid in enumerate(retrieved[:k]) if rid in relevant
    )
    ideal_hits = min(k, len(relevant))
    idcg = sum(1.0 / math.log2(rank + 2.0) for rank in range(ideal_hits))
    return dcg / idcg


def mrr_at_k(retrieved: Sequence[str], relevant: frozenset[str] | set[str], k: int) -> float:
    if not relevant:
        return 1.0
    for rank, rid in enumerate(retrieved[:k]):
        if rid in relevant:
            return 1.0 / (rank + 1.0)
    return 0.0


def ordered_unique(values: Sequence[str]) -> list[str]:
    """Order-preserving dedup — maps a ranked doc list to a ranked session list."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
