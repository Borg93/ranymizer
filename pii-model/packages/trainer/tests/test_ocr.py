# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the span-preserving OCR-noise augmenter (`ocr_noise`).

The core contract: every mention in the returned entities must be a verbatim
substring of the noised text — by construction, not by filtering.
"""

from __future__ import annotations

import random

import pytest
from ranymizer_trainer.ocr import ocr_noise

# (text, {label: [mention, ...]}) — tables, diacritics, multi-occurrence, empty.
ROWS: list[tuple[str, dict[str, list[str]]]] = [
    (
        "Namn | Personnummer\nSven Andersson | 850315-2384",
        {"person": ["Sven Andersson"], "personnummer": ["850315-2384"]},
    ),
    (
        "Kontaktperson: Åsa Öberg, e-post: asa.oberg@example.se",
        {"person": ["Åsa Öberg"], "email": ["asa.oberg@example.se"]},
    ),
    ("Organisationsnummer: 556677-8899", {"organisationsnummer": ["556677-8899"]}),
    ("Telefon: 070-123 45 67", {"phone": ["070-123 45 67"]}),
    (
        "Adress | Stad\nStorgatan 12, 11122 Stockholm | Stockholm",
        {"address": ["Storgatan 12, 11122 Stockholm"]},
    ),
    (
        "Patienten Björn Lindberg har diagnos diabetes typ 2.",
        {"person": ["Björn Lindberg"], "health": ["diabetes typ 2"]},
    ),
    ("Bankgiro: 5050-1055 Plusgiro: 90 20 02-2", {"bank": ["5050-1055", "90 20 02-2"]}),
    (
        "Se https://www.bolagsverket.se for mer information.",
        {"url": ["https://www.bolagsverket.se"]},
    ),
    (
        "Domen: villkorlig dom samt dagsböter.",
        {"criminal": ["villkorlig dom", "dagsböter"]},
    ),
    ("Medlem i Svenska kyrkan sedan 1998.", {"religion_ethnicity": ["Svenska kyrkan"]}),
    # Multi-occurrence: same mention twice.
    (
        "Anna Svensson ringde. Anna Svensson svarade inte.",
        {"person": ["Anna Svensson"]},
    ),
    # Substring-of-substring: "Anna" is inside "Anna Svensson".
    ("Anna Svensson och Anna jobbar ihop.", {"person": ["Anna Svensson", "Anna"]}),
    ("Detta är en rad helt utan PII alls.", {}),
    ("Beslutsdatum: 2024-05-20 enligt protokoll.", {"date": ["2024-05-20"]}),
]


@pytest.mark.parametrize(("text", "entities"), ROWS)
def test_every_noised_mention_is_a_substring(
    text: str, entities: dict[str, list[str]]
) -> None:
    noised_text, noised_entities = ocr_noise(
        text, entities, random.Random(1234), rate=0.12
    )
    for label, mentions in noised_entities.items():
        for mention in mentions:
            assert mention in noised_text, f"[{label}] {mention!r} not in noised text"


def test_noise_changes_at_least_one_row() -> None:
    changed = any(
        ocr_noise(text, ents, random.Random(1000 + i), rate=0.12)[0] != text
        for i, (text, ents) in enumerate(ROWS)
    )
    assert changed


def test_deterministic_for_same_seed() -> None:
    text, ents = ROWS[0]
    a = ocr_noise(text, ents, random.Random(7), rate=0.12)
    b = ocr_noise(text, ents, random.Random(7), rate=0.12)
    assert a == b


def test_empty_entities_stay_empty() -> None:
    _, noised_entities = ocr_noise(
        "Helt vanlig text utan PII.", {}, random.Random(3), rate=0.2
    )
    assert noised_entities == {}


def test_multi_occurrence_dedup() -> None:
    text, ents = ROWS[10]
    _, noised_entities = ocr_noise(text, ents, random.Random(5), rate=0.0)
    assert noised_entities["person"] == ["Anna Svensson"]


def test_rate_zero_is_identity() -> None:
    text, ents = ROWS[0]
    noised_text, noised_entities = ocr_noise(text, ents, random.Random(0), rate=0.0)
    assert noised_text == text
    assert noised_entities == {
        "person": ["Sven Andersson"],
        "personnummer": ["850315-2384"],
    }
