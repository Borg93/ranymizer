# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Derive the non-NER GLiNER2 task families from the recipe's {text, entities}.

GLiNER2 is multi-task (entities, classifications, json_structures, relations).
The recipe's single LLM call yields {text, entities} — the NER task. The other
three families are **pure deterministic projections** of that output (plus the
`seed_company` value for the employer field), so one 100k-row generation pass
yields ~100k examples for *every* task family at zero extra token cost.

This module is intentionally dependency-free (stdlib + the label vocabulary
only) so it unit-tests in any venv. `scripts/02_to_gliner2_jsonl.py` wraps the
plain dicts/tuples returned here into gliner2 `Classification` / `Structure` /
`Relation` objects.

Design decisions (verified against the GLiNER2 format + an adversarial review):
  - Multi-subject rows are NOT merged into one record/owner graph — the
    generation prompt only forbids grouping people by a *sensitive* attribute,
    so a non-sensitive 2-person table row is legal. We drop the structures /
    relations tasks for such rows (entities + classification still apply) rather
    than corrupt name↔identifier pairing.
  - Entity-mention parsing tolerates dict / JSON string / Python-repr string,
    because the NDD `entities` expression column's on-the-wire form is
    engine-dependent.
"""

from __future__ import annotations

import ast
import json
import re
from typing import TypedDict

from ranymizer_pii_core import (
    LABEL_NAMES as LABELS,
)
from ranymizer_pii_core import (
    PERSON_IDENTIFIER_FIELDS,
    Sensitivity,
    names_with,
)

# ── Sensitivity (classification) taxonomy ──────────────────────────────────
# WHICH labels fall in which tier comes from core (single source of truth); only
# the gliner2 classification-LABEL STRING per tier is a trainer concern. We map
# each Art. 9 / Art. 10 sensitivity tier to its classification label string here.
_TIER_TO_CLASS_LABEL: dict[Sensitivity, str] = {
    Sensitivity.ART9_HEALTH: "art9_health",
    Sensitivity.ART9_BELIEF: "art9_religion_ethnicity",
    Sensitivity.ART10_CRIMINAL: "art10_criminal",
}

DIRECT_PII_LABELS = set(names_with(Sensitivity.DIRECT))
# Art. 9 / Art. 10 entity label → sensitivity class (derived from core tiers).
_SENS_MAP = {
    name: class_label
    for tier, class_label in _TIER_TO_CLASS_LABEL.items()
    for name in names_with(tier)
}
# In LABELS but neither a direct identifier nor special-category data.
_IGNORED_LABELS = set(names_with(Sensitivity.CONTEXTUAL))

SENSITIVITY_LABELS = [
    "direct_pii",
    "art9_health",
    "art9_religion_ethnicity",
    "art10_criminal",
    "no_sensitive",
]
SENSITIVITY_LABEL_DESCRIPTIONS = {
    "direct_pii": "Fragment contains a direct identifier (name, email, phone, address, personnummer, organisationsnummer, or bank/giro/IBAN).",
    "art9_health": "Fragment contains GDPR Art. 9 health data (diagnosis, medication, treatment, disability, sick leave, mental health).",
    "art9_religion_ethnicity": "Fragment contains GDPR Art. 9 religion, philosophical conviction, ethnic origin, or trade-union membership.",
    "art10_criminal": "Fragment contains GDPR Art. 10 criminal-offence / conviction data (misstanke, åtal, dom, påföljd).",
    "no_sensitive": "Fragment contains no direct identifier and no Art. 9 / Art. 10 special-category data.",
}

# Person-owned identifiers/attributes for the `belongs_to` relation. Excludes
# organisationsnummer / bank (company-owned), date (an event), url (institutional).
# Sensitive labels (health/criminal/religion_ethnicity) are masked via entities /
# classification only — never linked via belongs_to — so the single-person path
# matches the multi-person records path (consistent identifier ownership). Sourced
# from core so the single-subject belongs_to set is identical to person_record's.
PERSON_OWNED_LABELS = PERSON_IDENTIFIER_FIELDS

# Fail loudly if LABELS grows but this taxonomy is not updated — otherwise a new
# sensitive label would silently fall through to `no_sensitive`.
_COVERED = DIRECT_PII_LABELS | set(_SENS_MAP) | _IGNORED_LABELS
if set(LABELS) != _COVERED:
    raise RuntimeError(
        f"task_families sensitivity taxonomy out of sync with LABELS: {set(LABELS) ^ _COVERED}"
    )


class SensitivityTask(TypedDict):
    """The multi-label `sensitivity` payload — splat into a gliner2 `Classification`.

    Keys mirror `Classification`'s constructor params, so `Classification(**payload)`
    is type-checked field-by-field.
    """

    task: str
    labels: list[str]
    true_label: list[str]
    multi_label: bool
    label_descriptions: dict[str, str]


def _parse_mapping(value: object) -> dict:
    """Best-effort dict from a value that may be a dict / JSON / Python-repr str."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        for parse in (json.loads, ast.literal_eval):
            try:
                parsed = parse(value)
            except (ValueError, SyntaxError):
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def coerce_entities(value: object) -> dict[str, list[str]]:
    """Parse an `entities` cell to ``{label: [mentions]}``, tolerating dict /
    JSON / Python-repr string forms (NDD's on-the-wire form is engine-dependent).
    Non-list values are dropped; returns ``{}`` when unparseable.
    """
    raw = _parse_mapping(value)
    return {
        str(k): [str(m) for m in v]
        for k, v in raw.items()
        if isinstance(v, (list, tuple))
    }


def _token_match(mention: str, text: str) -> bool:
    """True if `mention` occurs in `text` on word-character boundaries.

    A bare ``mention in text`` false-positives when a short numeric id is a
    substring of a longer number (e.g. ``"1234"`` inside ``"81234567"``). We
    require a non-word-character (or string edge) on both sides, so the match is
    a standalone token. Behaviour is identical to the substring test for normal
    multi-char alphanumeric mentions delimited by spaces/punctuation.
    """
    if not mention:
        return False
    return re.search(rf"(?<!\w){re.escape(mention)}(?!\w)", text) is not None


def _in_text(entities: dict[str, list[str]], text: str, label: str) -> list[str]:
    """Verbatim, in-text, de-duplicated (order-preserving) mentions for a label."""
    seen: set[str] = set()
    out: list[str] = []
    for mention in entities.get(label) or []:
        if mention and _token_match(mention, text) and mention not in seen:
            seen.add(mention)
            out.append(mention)
    return out


def derive_sensitivity(text: str, entities: dict[str, list[str]]) -> SensitivityTask:
    """Multi-label sensitivity classification payload (always >=1 true_label)."""
    present: set[str] = set()
    for label in entities:
        if not _in_text(entities, text, label):
            continue
        if label in _SENS_MAP:
            present.add(_SENS_MAP[label])
        elif label in DIRECT_PII_LABELS:
            present.add("direct_pii")
        # _IGNORED_LABELS (date/url) contribute nothing.
    true_label = [lab for lab in SENSITIVITY_LABELS if lab in present] or [
        "no_sensitive"
    ]
    return {
        "task": "sensitivity",
        "labels": list(SENSITIVITY_LABELS),
        "true_label": true_label,
        "multi_label": True,
        "label_descriptions": dict(SENSITIVITY_LABEL_DESCRIPTIONS),
    }


def derive_person_record(
    text: str, entities: dict[str, list[str]], seed_company: object = None
) -> dict[str, object] | None:
    """Identity-record fields for a single-subject row, else ``None``.

    Drops the task on multi-person rows (ambiguous identifier ownership). Identity
    fields are single-valued; only `address` may be a list (street/postnr/city
    fragments). `employer` is recovered from the seed company name (no entity
    label exists for it) and gated on a >=2-token verbatim match.
    """
    persons = _in_text(entities, text, "person")
    if len(persons) > 1:
        return None

    record: dict[str, object] = {}
    if persons:
        record["name"] = persons[0]
    for field, label in (
        ("personnummer", "personnummer"),
        ("phone", "phone"),
        ("email", "email"),
    ):
        mentions = _in_text(entities, text, label)
        if mentions:
            record[field] = mentions[0]
    address = _in_text(entities, text, "address")
    if address:
        record["address"] = address[0] if len(address) == 1 else address
    employer = _employer_name(seed_company, text)
    if employer:
        record["employer"] = employer

    return record or None


def _employer_name(seed_company: object, text: str) -> str | None:
    name = _parse_mapping(seed_company).get("name")
    # Require >=2 tokens to avoid a short single-token name matching unrelated text.
    if isinstance(name, str) and len(name.split()) >= 2 and name in text:
        return name
    return None


def derive_belongs_to(
    text: str, entities: dict[str, list[str]]
) -> list[tuple[str, str]]:
    """`(head, tail)` ownership edges for a single-subject row, else ``[]``."""
    persons = _in_text(entities, text, "person")
    if len(persons) != 1:
        return []
    tail = persons[0]
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for label in PERSON_OWNED_LABELS:
        for span in _in_text(entities, text, label):
            if span == tail or (span, label) in seen:
                continue
            seen.add((span, label))
            pairs.append((span, tail))
    return pairs
