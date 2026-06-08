# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Random-but-realistic generators for Swedish PII seed values.

The `make_*` functions are pure helpers (importable for unit tests without
pulling in `data_designer`). The `gen_seed_*` functions are NDD-decorated
row generators registered as `CustomColumnConfig` in the recipe.
"""

from __future__ import annotations

import random

import data_designer.config as dd

from .labels import CompanySeed
from .seed_pools import (
    _COMPANY_PREFIXES,
    _COMPANY_TRADES,
    _DOMAINS,
    _SWEDISH_CITIES,
    _SWEDISH_FIRST_NAMES,
    _SWEDISH_STREETS,
    _SWEDISH_SURNAMES,
)


def _swedish_full_name() -> str:
    return f"{random.choice(_SWEDISH_FIRST_NAMES)} {random.choice(_SWEDISH_SURNAMES)}"


def _email_from_name(name: str) -> str:
    slug = (
        name.lower()
        .replace(" ", ".")
        .replace("å", "a")
        .replace("ä", "a")
        .replace("ö", "o")
    )
    return f"{slug}@{random.choice(_DOMAINS)}"


def _luhn_check_digit(digits: str) -> str:
    """Compute the Luhn check digit for the first 9 digits of a personnummer."""
    s = 0
    for i, ch in enumerate(digits):
        n = int(ch) * (2 if i % 2 == 0 else 1)
        s += n if n < 10 else n - 9
    return str((10 - s % 10) % 10)


def make_personnummer() -> str:
    """Random valid-looking personnummer YYYYMMDD-XXXX with correct Luhn check."""
    year = random.randint(1940, 2010)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    serial = random.randint(0, 999)
    body = f"{year:04d}{month:02d}{day:02d}{serial:03d}"
    check = _luhn_check_digit(body[2:])  # Luhn is over last 9 (YYMMDDSSS)
    return f"{year:04d}{month:02d}{day:02d}-{serial:03d}{check}"


def make_orgnummer() -> str:
    """Random org. number XXXXXX-XXXX (no real-world checksum enforcement)."""
    return f"{random.randint(100000, 999999)}-{random.randint(1000, 9999)}"


def make_bankgiro() -> str:
    """Random bankgiro NNN-NNNN or NNNN-NNNN."""
    if random.random() < 0.5:
        return f"{random.randint(100, 999)}-{random.randint(1000, 9999)}"
    return f"{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"


def make_address() -> dict[str, str]:
    street = random.choice(_SWEDISH_STREETS)
    number = str(random.randint(1, 99))
    city, postnr = random.choice(_SWEDISH_CITIES)
    return {
        "street_line": f"{street} {number}",
        "postnr": postnr,
        "city": city,
        "full": f"{street} {number}, {postnr} {city}",
    }


def make_phone() -> str:
    style = random.choice(["mobile_dash", "mobile_plus", "landline"])
    if style == "mobile_dash":
        return f"070-{random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"
    if style == "mobile_plus":
        return f"+46 70 {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"
    return f"08-{random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"


# =============================================================================
# NDD row generators
# =============================================================================
#
# We declare `required_columns=["text_type"]` on every generator so NDD's
# async scheduler dispatches them as per-cell tasks. Without an upstream
# dependency the scheduler routes "no-dependency" custom columns through
# the from_scratch / FULL_COLUMN path and passes a DataFrame, which clashes
# with the default CELL_BY_CELL strategy. `text_type` is the very first
# diversifier and always present, so the dependency is essentially free.


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_person(row: dict) -> dict:
    row["seed_person"] = _swedish_full_name()
    return row


@dd.custom_column_generator(required_columns=["seed_person"])
def gen_seed_email(row: dict) -> dict:
    row["seed_email"] = _email_from_name(row["seed_person"])
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_phone(row: dict) -> dict:
    row["seed_phone"] = make_phone()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_personnummer(row: dict) -> dict:
    row["seed_personnummer"] = make_personnummer()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_company(row: dict) -> dict:
    row["seed_company"] = CompanySeed(
        name=f"{random.choice(_COMPANY_PREFIXES)} {random.choice(_COMPANY_TRADES)} AB",
        org_nr=make_orgnummer(),
        bankgiro=make_bankgiro(),
    ).model_dump()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_address(row: dict) -> dict:
    row["seed_address"] = make_address()
    return row
