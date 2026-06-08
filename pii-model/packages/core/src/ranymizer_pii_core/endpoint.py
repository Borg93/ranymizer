# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""The LLM endpoint — injected into synthesis (generation) and evaluation (judge).

Never hardcode an endpoint inside a stage. The CLI builds one `ModelEndpoint`
from flags/env and passes it down, so the same value object drives both the
generator and the judge, and pointing at a different server is a one-line change.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelEndpoint(BaseModel):
    """An OpenAI-compatible chat endpoint (vLLM / Ollama / llama.cpp / OpenAI)."""

    base_url: str = Field(
        description="OpenAI-compatible base, e.g. http://localhost:8003/v1"
    )
    model: str = Field(description="Served model id, e.g. google/gemma-4-31B-it")
    api_key: str = Field(
        default="not-needed",
        description="Local servers ignore this, but the OpenAI client needs a non-empty string.",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1536, gt=0)
    timeout: int = Field(default=300, gt=0)
    max_parallel_requests: int = Field(default=8, ge=1)
