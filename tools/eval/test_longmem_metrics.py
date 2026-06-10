"""Metric pure-function tests — Stream CM-N5 P0."""

from __future__ import annotations

import pytest
from longmem.metrics import mrr_at_k, ndcg_at_k, ordered_unique, recall_at_k


def test_recall_partial_and_perfect() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "c"}, 3) == 1.0
    assert recall_at_k(["a", "b", "c"], {"a", "z"}, 3) == 0.5
    assert recall_at_k(["a", "b", "c"], {"z"}, 3) == 0.0


def test_recall_respects_k() -> None:
    assert recall_at_k(["x", "a"], {"a"}, 1) == 0.0
    assert recall_at_k(["x", "a"], {"a"}, 2) == 1.0


def test_empty_relevance_is_a_noop_case() -> None:
    assert recall_at_k(["a"], frozenset(), 5) == 1.0
    assert ndcg_at_k(["a"], frozenset(), 5) == 1.0
    assert mrr_at_k(["a"], frozenset(), 5) == 1.0


def test_k_zero_scores_zero() -> None:
    assert recall_at_k(["a"], {"a"}, 0) == 0.0
    assert ndcg_at_k(["a"], {"a"}, 0) == 0.0
    assert mrr_at_k(["a"], {"a"}, 0) == 0.0


def test_ndcg_rewards_rank() -> None:
    top = ndcg_at_k(["a", "x", "y"], {"a"}, 3)
    low = ndcg_at_k(["x", "y", "a"], {"a"}, 3)
    assert top == 1.0
    assert 0.0 < low < top


def test_ndcg_multi_relevant_ideal_normalisation() -> None:
    # Both relevant docs at the top -> perfect score even with k > |relevant|.
    assert ndcg_at_k(["a", "b", "x"], {"a", "b"}, 3) == pytest.approx(1.0)


def test_mrr_rank_positions() -> None:
    assert mrr_at_k(["a", "x"], {"a"}, 5) == 1.0
    assert mrr_at_k(["x", "a"], {"a"}, 5) == 0.5
    assert mrr_at_k(["x", "y"], {"a"}, 5) == 0.0


def test_ordered_unique_preserves_first_occurrence() -> None:
    assert ordered_unique(["s2", "s1", "s2", "s3", "s1"]) == ["s2", "s1", "s3"]
    assert ordered_unique([]) == []
