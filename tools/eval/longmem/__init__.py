"""Stream CM-N5 — LongMemEval + LoCoMo memory-benchmark harness.

Two evaluation tiers (STREAM-CM-DESIGN §12):

- **P0 retrieval tier** (this package's ``retrieval`` module): zero-LLM
  mechanical regression gate. Ground truth comes from the benchmarks'
  own annotations (``answer_session_ids`` / ``has_answer`` / ``evidence``),
  so Recall@k / NDCG@k / MRR are pure computations. The ablation matrix
  (decay x MMR x rerank x hybrid) attributes CM-4 / CM-6 component gains
  without end-to-end noise.
- **P1 end-to-end tier** (CM-N5 PR3): LLM ingestion via
  ``flush_messages_to_memory(reconcile=True)`` + reading + judge — the
  cross-vendor comparable number.

Datasets are **not vendored** (Mini-ADR CM-K3: LoCoMo is CC BY-NC, the
LongMemEval_S file is 277MB) — ``download`` fetches them into a
gitignored cache with sha256 pinning. CI exercises the pipeline against
the tiny synthetic fixtures under ``datasets/longmem_fixture/`` only.
"""
