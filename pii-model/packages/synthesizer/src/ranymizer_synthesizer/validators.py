# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Cheap, deterministic substring validator for the generated rows.

The judge handles soft quality (Swedish fluency, label completeness). This
validator handles the hard "did the LLM hallucinate a mention" check.
"""

from __future__ import annotations

import ast
import json

import data_designer.config as dd
from ranymizer_pii_core import PERSON_IDENTIFIER_FIELDS

from .schema import canonical_sparse_entities


@dd.custom_column_generator(required_columns=["generation"])
def flatten_entities(row: dict) -> dict:
    """Flatten ``generation.entities`` into a canonical SPARSE JSON-string column.

    The LLM emits a free, sparse ``{label: mentions}`` object (only the labels it
    used — fewer decode tokens). We serialise it to a JSON string in Python rather
    than via a Jinja `{{ generation.entities }}` expression because NDD infers a
    parquet *struct* from a dict column, which fails on the empty / no-PII rows
    ("Cannot write struct type 'entities' with no child field"). A string column
    is stable, and every consumer already parses it back via ``ast.literal_eval``
    / ``json.loads``.
    """
    gen = row.get("generation")
    raw = gen.get("entities") if isinstance(gen, dict) else getattr(gen, "entities", None)
    row["entities"] = json.dumps(canonical_sparse_entities(raw), ensure_ascii=False)
    return row


def _parse_entities(value: str) -> object:
    """Parse the entities cell tolerating both JSON and Python-repr strings.

    NDD's expression engine may serialise the dict as JSON (double quotes) or a
    Python repr (single quotes) depending on the path; trying both avoids
    silently failing validation — and dropping every row — on the repr form.
    """
    for parse in (json.loads, ast.literal_eval):
        try:
            return parse(value)
        except (ValueError, SyntaxError):
            continue
    return None


@dd.custom_column_generator(
    required_columns=["text", "entities"],
)
def validate_entities(row: dict) -> dict:
    """True iff every mention in `entities` is a substring (case-sensitive) of `text`."""
    text = row["text"]
    ents = row["entities"]
    if isinstance(ents, str):
        ents = _parse_entities(ents)
    if not isinstance(ents, dict):
        row["entities_validated"] = False
        return row
    for _label, mentions in ents.items():
        if not isinstance(mentions, (list, tuple)):
            continue
        for m in mentions:
            # Mentions can arrive as non-strings (the model emits bare numbers
            # for card_number / amounts), so coerce before the substring test —
            # `int not in str` raises TypeError and would drop the whole row.
            if m is None:
                continue
            if str(m) not in text:
                row["entities_validated"] = False
                return row
    row["entities_validated"] = True
    return row


# `address` is checked separately and loosely: the model often splits the
# street and city across lines, so record.address may be a substring of the
# seed (or vice-versa). A substring match still proves the row came from this
# subject's seed without dropping otherwise-valid rows.
_RECORD_ADDRESS_FIELD = "address"

# Identifier fields that link a record back to a single seed subject. `name`
# is excluded (it's the key used to look up the seed) and `address` is excluded
# (checked loosely above), so this is derived from core's identifier set rather
# than re-typed here — it can't drift from the canonical taxonomy. These must
# match the seed EXACTLY (no swap): a loosened compare would let the model emit
# one person's id on another's record.
_RECORD_IDENTIFIER_FIELDS = tuple(
    f for f in PERSON_IDENTIFIER_FIELDS if f != _RECORD_ADDRESS_FIELD
)


def _norm(text: str) -> str:
    """Collapse whitespace and lowercase for loose address comparison."""
    return " ".join(text.split()).casefold()


def _address_matches(record_value: str, seed_value: str) -> bool:
    """True iff the record address is a non-trivial substring of the seed (or vice-versa).

    Whitespace is normalised and case is folded first. An empty record value
    is treated as "no claim" (matching) so a missing address never blocks a
    row; the verbatim-in-text grounding check still applies separately.
    """
    rec = _norm(record_value)
    if not rec:
        return True
    seed = _norm(seed_value)
    if not seed:
        return False
    return rec == seed or (rec in seed) or (seed in rec)


def _as_dict_list(value: object) -> list[dict[str, str]] | None:
    """Coerce a records / seed_subjects cell to a list of ``{str: str}`` dicts.

    Returns ``None`` (fail closed) when the cell is not a list of dicts. ``None``
    field values are dropped so a missing identifier never blocks validation.
    """
    if isinstance(value, str):
        value = _parse_entities(value)
    if not isinstance(value, (list, tuple)):
        return None
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        out.append({str(k): str(v) for k, v in item.items() if v is not None})
    return out


@dd.custom_column_generator(
    required_columns=["text", "records", "seed_subjects"],
)
def validate_records(row: dict) -> dict:
    """True iff every record field is verbatim in `text` AND matches that person's seed."""
    text = row["text"]
    records = _as_dict_list(row.get("records"))
    seed_subjects = _as_dict_list(row.get("seed_subjects"))
    if records is None or seed_subjects is None:
        row["records_validated"] = False
        return row

    seeds: dict[str, dict[str, str]] = {
        name: subject
        for subject in seed_subjects
        if isinstance(name := subject.get("name"), str)
    }
    ok = True
    for rec in records:
        if any(value and value not in text for value in rec.values()):  # (a) grounding
            ok = False
            break
        name = rec.get("name")
        seed = seeds.get(name) if name is not None else None
        if (
            seed is None
            or any(  # (b) identifiers must match THAT person's seed (no swap)
                rec.get(f) and rec.get(f) != seed.get(f)
                for f in _RECORD_IDENTIFIER_FIELDS
            )
        ):
            ok = False
            break
        addr = rec.get(_RECORD_ADDRESS_FIELD)  # (b') address: loose substring match
        if addr and not _address_matches(addr, seed.get(_RECORD_ADDRESS_FIELD, "")):
            ok = False
            break
    row["records_validated"] = ok
    return row
