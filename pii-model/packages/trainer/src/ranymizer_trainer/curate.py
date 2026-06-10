# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Semantic near-duplicate detection for synthetic rows via a local embedding model.

One layer of the data-curation stack (the others: the deterministic grounding
check already in :mod:`convert`, and the deepeval LLM judge). LLM-generated data
mode-collapses into near-paraphrases that an exact-text drop misses; this embeds
each row's text with a local OpenAI-compatible endpoint (e.g.
``Qwen/Qwen3-VL-Embedding-2B`` on :8001) and drops rows whose nearest *kept*
neighbour exceeds a cosine threshold.

Brute-force numpy is fine to ~50k rows; for millions swap the inner search for a
faiss ANN index (the public API here stays the same).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from openai import OpenAI
from pydantic import BaseModel, Field


class EmbeddingEndpoint(BaseModel):
    """A local OpenAI-compatible embeddings endpoint (separate from the gen/judge LLM)."""

    base_url: str = "http://localhost:8001/v1"
    model: str = "Qwen/Qwen3-VL-Embedding-2B"
    api_key: str = "not-needed"
    batch_size: int = Field(default=64, ge=1)


class DedupResult(BaseModel):
    """Outcome of a near-dup pass."""

    total: int
    kept: int
    dropped: int
    threshold: float


def embed_texts(texts: Sequence[str], endpoint: EmbeddingEndpoint) -> np.ndarray:
    """Return L2-normalised embeddings (so a dot product is the cosine similarity)."""
    client = OpenAI(base_url=endpoint.base_url, api_key=endpoint.api_key)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), endpoint.batch_size):
        chunk = list(texts[start : start + endpoint.batch_size])
        response = client.embeddings.create(model=endpoint.model, input=chunk)
        vectors.extend(item.embedding for item in response.data)
    arr = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / np.clip(norms, 1e-12, None)


def near_dup_keep_mask(embeddings: np.ndarray, threshold: float = 0.95) -> np.ndarray:
    """Greedy keep-mask: drop a row if it is ≥ ``threshold`` cosine of an earlier kept row.

    The first occurrence of a near-dup cluster is kept; the rest are dropped.
    """
    n = len(embeddings)
    keep = np.ones(n, dtype=bool)
    for i in range(n):
        if not keep[i]:
            continue
        if i + 1 >= n:
            break
        sims = embeddings[i + 1 :] @ embeddings[i]
        dup_local = np.nonzero(sims >= threshold)[0]
        keep[dup_local + i + 1] = False
    return keep


def dedup_texts(
    texts: Sequence[str],
    *,
    endpoint: EmbeddingEndpoint | None = None,
    threshold: float = 0.95,
) -> tuple[np.ndarray, DedupResult]:
    """Embed ``texts`` and return ``(keep_mask, DedupResult)`` for semantic near-dups."""
    endpoint = endpoint or EmbeddingEndpoint()
    embeddings = embed_texts(texts, endpoint)
    keep = near_dup_keep_mask(embeddings, threshold)
    kept = int(keep.sum())
    return keep, DedupResult(
        total=len(texts), kept=kept, dropped=len(texts) - kept, threshold=threshold
    )
