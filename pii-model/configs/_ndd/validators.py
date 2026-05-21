# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Cheap, deterministic substring validator for the generated rows.

The judge handles soft quality (Swedish fluency, label completeness). This
validator handles the hard "did the LLM hallucinate a mention" check.
"""

from __future__ import annotations

import json

import data_designer.config as dd


@dd.custom_column_generator(
    required_columns=["text", "entities"],
)
def validate_entities(row: dict) -> dict:
    """True iff every mention in `entities` is a substring (case-sensitive) of `text`."""
    text = row["text"]
    ents = row["entities"]
    if isinstance(ents, str):
        try:
            ents = json.loads(ents)
        except Exception:
            row["entities_validated"] = False
            return row
    if not isinstance(ents, dict):
        row["entities_validated"] = False
        return row
    for _label, mentions in ents.items():
        for m in mentions or []:
            if m and m not in text:
                row["entities_validated"] = False
                return row
    row["entities_validated"] = True
    return row
