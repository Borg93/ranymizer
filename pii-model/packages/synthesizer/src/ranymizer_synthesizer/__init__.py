# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Config-driven synthetic Swedish-PII data generator.

The centerpiece of the workspace: a :class:`SynthesisConfig` declares *what* to
synthesise (label set, genres, registers, layouts, whether to judge), and
:func:`build_recipe` + :func:`create` / :func:`preview` turn that into a NeMo Data Designer run
against an injected :class:`~ranymizer_pii_core.ModelEndpoint`. The label
vocabulary comes from ``ranymizer_pii_core``; nothing is re-declared here.
"""

from __future__ import annotations

from ranymizer_synthesizer.config import SynthesisConfig
from ranymizer_synthesizer.recipe import build_recipe
from ranymizer_synthesizer.run import create, preview
from ranymizer_synthesizer.seeds import FAKER_LOCALE, faker_version

__all__ = [
    "FAKER_LOCALE",
    "SynthesisConfig",
    "build_recipe",
    "create",
    "faker_version",
    "preview",
]
