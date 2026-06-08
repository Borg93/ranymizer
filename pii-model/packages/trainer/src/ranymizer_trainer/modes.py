# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Training-strategy enum.

Kept in its own gliner2-free module so the CLI can validate ``--mode`` at parse
time (and offer it as a typed choice) without importing torch/gliner2.
"""

from __future__ import annotations

from enum import StrEnum


class TrainMode(StrEnum):
    """GLiNER2 training strategy."""

    LORA = "lora"  # ~5 MB adapter, fast pilot
    FULL = "full"  # ~450 MB full fine-tune, slower
