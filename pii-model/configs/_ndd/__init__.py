# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Internal modules for the Swedish PII recipe.

The public surface lives in `configs.ndd_swedish_pii` (importable as
`from configs.ndd_swedish_pii import build_config, LABELS, …`). This
package is underscore-prefixed to discourage direct import from outside
the recipe.

Layout:
    labels.py            — LABELS, LABEL_DESCRIPTIONS, pydantic output models.
    seed_pools.py        — static seed lists (names, streets, cities, sensitive pools).
    seed_generators.py   — Luhn-valid personnummer + the NDD-decorated row generators.
    validators.py        — substring validator (entities_validated).
    prompts.py           — text-generation + LLM-judge prompts & rubrics.
"""
