# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Where the LLM endpoint VALUE lives — the one place, never a stage.

`core.ModelEndpoint` defines the *shape*; this defines the *value* (defaults to
this box's local Gemma-4 vLLM at http://localhost:8003/v1), overridable by env
(`RANYMIZER_BASE_URL` / `RANYMIZER_MODEL` / `RANYMIZER_API_KEY`) or per-command
CLI flags. Build an endpoint with ``settings.endpoint(base_url=..., model=...)``.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from ranymizer_pii_core import ModelEndpoint


class Settings(BaseSettings):
    """Runtime configuration for the CLI (env-overridable; sensible local defaults)."""

    base_url: str = "http://localhost:8003/v1"
    model: str = "google/gemma-4-31B-it"
    api_key: str = "not-needed"

    model_config = SettingsConfigDict(
        env_prefix="RANYMIZER_",
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),  # allow a field literally named `model`
    )

    def endpoint(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> ModelEndpoint:
        """A `ModelEndpoint`, with any non-None overrides applied on top."""
        overrides = {"base_url": base_url, "model": model, "api_key": api_key}
        values: dict[str, object] = {
            "base_url": self.base_url,
            "model": self.model,
            "api_key": self.api_key,
        }
        values.update({k: v for k, v in overrides.items() if v is not None})
        return ModelEndpoint.model_validate(values)


settings = Settings()
