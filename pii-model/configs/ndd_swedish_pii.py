# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""
NeMo Data Designer recipe — Swedish PII training data for GLiNER2.

Mirrors the pattern from NDD's own recipes (e.g. `multi_turn_chat.py`,
`enterprise_text_to_sql.py`): build a `DataDesignerConfigBuilder`, add
diversifier columns + LLM columns, return it. Train wiring lives in
`scripts/01_generate_synthetic.py`.

Output parquet has columns:
  - seed_*               : the realistic PII values we want to plant in the text
  - text_type, register  : diversifiers
  - text                 : the generated training sentence
  - entities             : {label: [mentions]} parsed from the LLM JSON
  - entities_validated   : True iff every mention is a substring of `text`

`scripts/02_to_gliner2_jsonl.py` drops rows with entities_validated=False
and converts the rest into gliner2 `InputExample` JSONL.

Prerequisites:
    - OPENAI_API_KEY (default), NVIDIA_API_KEY, or a local vLLM endpoint.
"""

from __future__ import annotations

import json
import random
from typing import Literal

from pydantic import BaseModel, Field

import data_designer.config as dd

# =============================================================================
# Labels — must match `frontend/src/lib/components/Landing.svelte`
# =============================================================================

LABELS = [
    "person",
    "email",
    "phone",
    "address",
    "personnummer",
    "organisationsnummer",
    "bank",
    "date",
    "url",
]

LABEL_DESCRIPTIONS = {
    "person": "Full name of an individual (given name + surname, or initials).",
    "email": "Email address, e.g. firstname.lastname@example.se.",
    "phone": "Phone number in Swedish or international format (+46, 070-..., 08-...).",
    "address": "Street address line(s): street name + number, postnummer, city.",
    "personnummer": "Swedish personal identity number (YYYYMMDD-XXXX or YYMMDD-XXXX).",
    "organisationsnummer": "Swedish organisation number (XXXXXX-XXXX).",
    "bank": "Bank account information: bankgiro, plusgiro, IBAN, BIC, clearing+account.",
    "date": "Calendar dates in Swedish format (2024-05-20, 20 maj 2024, etc).",
    "url": "Web URLs (https://..., www....).",
}

# =============================================================================
# Helpers: realistic seed generators
# =============================================================================

# Tiny on-device samplers used as Expressions in the recipe.
# Kept small/inline so the recipe stays self-contained; if we ever need
# fancier ones (Luhn-checksummed personnummer, valid IBAN), promote them
# into NDD CustomColumn plugins.

_SWEDISH_FIRST_NAMES = [
    "Anna", "Erik", "Maria", "Lars", "Karin", "Anders", "Eva", "Johan",
    "Sara", "Mikael", "Linda", "Per", "Helena", "Magnus", "Emma", "Daniel",
    "Sofia", "Andreas", "Lena", "Mattias", "Ingrid", "Stefan", "Margareta",
    "Niklas", "Astrid", "Oskar", "Greta", "Henrik",
]

_SWEDISH_SURNAMES = [
    "Andersson", "Johansson", "Karlsson", "Nilsson", "Eriksson", "Larsson",
    "Olsson", "Persson", "Svensson", "Gustafsson", "Pettersson", "Jonsson",
    "Jansson", "Lindberg", "Lindgren", "Lindström", "Lindqvist", "Bergström",
    "Berglund", "Sandberg", "Forsberg", "Sjöberg", "Wallin", "Ek", "Ek borg",
]

_SWEDISH_STREETS = [
    "Storgatan", "Kungsgatan", "Drottninggatan", "Sveavägen", "Vasagatan",
    "Östermalmstorg", "Götgatan", "Hornsgatan", "Birger Jarlsgatan",
    "Strandvägen", "Folkungagatan", "Tegnérgatan", "Karlavägen", "Valhallavägen",
]

_SWEDISH_CITIES = [
    ("Stockholm", "111 22"), ("Göteborg", "411 03"), ("Malmö", "211 18"),
    ("Uppsala", "753 21"), ("Linköping", "582 19"), ("Västerås", "722 12"),
    ("Örebro", "702 11"), ("Norrköping", "602 21"), ("Helsingborg", "252 25"),
    ("Lund", "222 22"), ("Umeå", "903 26"), ("Gävle", "802 67"),
]

_DOMAINS = ["gmail.com", "outlook.com", "hotmail.com", "telia.com", "icloud.com"]


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
# Structured outputs
# =============================================================================


class CompanySeed(BaseModel):
    name: str = Field(..., description="Realistic Swedish company name (AB).")
    org_nr: str = Field(..., description="Org. number XXXXXX-XXXX.")
    bankgiro: str = Field(..., description="Bankgiro NNN-NNNN or NNNN-NNNN.")


class EntitiesOutput(BaseModel):
    """LLM-returned entities. Each mention MUST be a verbatim substring of `text`."""

    person: list[str] = Field(default_factory=list)
    email: list[str] = Field(default_factory=list)
    phone: list[str] = Field(default_factory=list)
    address: list[str] = Field(default_factory=list)
    personnummer: list[str] = Field(default_factory=list)
    organisationsnummer: list[str] = Field(default_factory=list)
    bank: list[str] = Field(default_factory=list)
    date: list[str] = Field(default_factory=list)
    url: list[str] = Field(default_factory=list)


# =============================================================================
# Custom column: substring validator
# =============================================================================


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


# =============================================================================
# Recipe
# =============================================================================

TEXT_GEN_SYSTEM_PROMPT = """\
You write realistic Swedish business/personal text fragments and label every PII span.
You return a single JSON object that obeys the response schema exactly.
NEVER invent PII values: only use the seed values provided in the user prompt.
Every entity mention MUST appear verbatim in the `text` field (same casing, same spacing).
"""

TEXT_GEN_PROMPT = """\
Write a single realistic Swedish {text_type} fragment in a {register} register, 1-3 sentences.
The fragment MUST naturally use SOME of these seed PII values (pick at least 2, at most all):

person:               {seed_person}
email:                {seed_email}
phone:                {seed_phone}
personnummer:         {seed_personnummer}
company name:         {seed_company.name}
organisationsnummer:  {seed_company.org_nr}
bankgiro:             {seed_company.bankgiro}
address (street):     {seed_address.street_line}
address (postnr):     {seed_address.postnr}
address (city):       {seed_address.city}
date:                 {seed_date}
url:                  {seed_url}

Then return a JSON object with:
  - text:     the fragment you wrote
  - entities: a dict mapping every PII label you actually used to the list of
              verbatim mentions in `text`. Labels you didn't use must be `[]`.

Labels:
  person, email, phone, address, personnummer, organisationsnummer, bank, date, url

Hard rules:
  1. Write Swedish (not English). Names, street, city stay in their original form.
  2. Every mention must be a verbatim substring of `text` — no rephrasing.
  3. Do not invent new PII values beyond the seeds.
  4. Address: you may include any of `street_line`, `postnr`, `city`, or the full address.
     Each one used must appear as its own mention under `entities.address`.
"""


def build_config(model_alias: str = "openai-text") -> dd.DataDesignerConfigBuilder:
    config = dd.DataDesignerConfigBuilder()

    # ─────────────────────────────────────────────────────────────────────
    # 1. Diversifiers
    # ─────────────────────────────────────────────────────────────────────
    config.add_column(
        dd.SamplerColumnConfig(
            name="text_type",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=[
                    "support email",
                    "invoice line",
                    "kontoutdrag entry",
                    "form screenshot caption",
                    "internal Slack message",
                    "customer ticket",
                    "kvitto/receipt note",
                    "id-kort preview text",
                    "address-change notification",
                    "doctor appointment summary",
                ],
                weights=[1.2, 1.0, 1.0, 1.0, 1.0, 1.2, 0.8, 0.6, 0.8, 0.8],
            ),
        )
    )

    config.add_column(
        dd.SamplerColumnConfig(
            name="register",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=["formal", "informal", "bureaucratic", "mobile chat"]
            ),
        )
    )

    # ─────────────────────────────────────────────────────────────────────
    # 2. Seed PII values — these are the real "ground truth"
    # ─────────────────────────────────────────────────────────────────────
    config.add_column(
        dd.ExpressionColumnConfig(
            name="seed_person",
            expr=(
                "{{ ['"
                + "', '".join(_SWEDISH_FIRST_NAMES)
                + "'] | random }} "
                "{{ ['"
                + "', '".join(_SWEDISH_SURNAMES)
                + "'] | random }}"
            ),
        )
    )

    config.add_column(
        dd.ExpressionColumnConfig(
            name="seed_email",
            expr=(
                "{{ seed_person.lower().replace(' ', '.').replace('å','a').replace('ä','a').replace('ö','o') }}"
                "@{{ ['"
                + "', '".join(_DOMAINS)
                + "'] | random }}"
            ),
        )
    )

    config.add_column(
        dd.CustomColumnConfig(
            name="seed_phone",
            generator_function=lambda _row: {"seed_phone": make_phone()},
        )
    )
    config.add_column(
        dd.CustomColumnConfig(
            name="seed_personnummer",
            generator_function=lambda _row: {"seed_personnummer": make_personnummer()},
        )
    )
    config.add_column(
        dd.CustomColumnConfig(
            name="seed_company",
            generator_function=lambda _row: {
                "seed_company": CompanySeed(
                    name=f"{random.choice(['Nordic', 'Svensk', 'Stockholm', 'Göteborgs', 'Skånes'])} "
                    f"{random.choice(['Konsult', 'Bygg', 'Handel', 'Service', 'Teknik'])} AB",
                    org_nr=make_orgnummer(),
                    bankgiro=make_bankgiro(),
                ).model_dump()
            },
        )
    )
    config.add_column(
        dd.CustomColumnConfig(
            name="seed_address",
            generator_function=lambda _row: {"seed_address": make_address()},
        )
    )

    config.add_column(
        dd.SamplerColumnConfig(
            name="seed_date",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=[
                    "2024-05-20",
                    "2025-01-15",
                    "20 maj 2024",
                    "15 januari 2025",
                    "2024-12-03",
                    "3 december 2024",
                ]
            ),
        )
    )

    config.add_column(
        dd.SamplerColumnConfig(
            name="seed_url",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=[
                    "https://www.skatteverket.se",
                    "https://swish.nu",
                    "https://www.bolagsverket.se",
                    "https://min.handelsbanken.se",
                    "https://www.fk.se",
                ]
            ),
        )
    )

    # ─────────────────────────────────────────────────────────────────────
    # 3. LLM column — write the text AND the labels in one call
    # ─────────────────────────────────────────────────────────────────────
    config.add_column(
        dd.LLMStructuredColumnConfig(
            name="generation",
            model_alias=model_alias,
            system_prompt=TEXT_GEN_SYSTEM_PROMPT,
            prompt=TEXT_GEN_PROMPT,
            output_format=TextWithEntities,
        )
    )

    # Split the structured output into flat columns for easier downstream use.
    config.add_column(dd.ExpressionColumnConfig(name="text", expr="{{ generation.text }}"))
    config.add_column(
        dd.ExpressionColumnConfig(name="entities", expr="{{ generation.entities }}")
    )

    # ─────────────────────────────────────────────────────────────────────
    # 4. Validator
    # ─────────────────────────────────────────────────────────────────────
    config.add_column(
        dd.CustomColumnConfig(
            name="entities_validated",
            generator_function=validate_entities,
        )
    )

    return config


class TextWithEntities(BaseModel):
    """Top-level LLM output for one row."""

    text: str = Field(..., description="The Swedish text fragment we generated.")
    entities: EntitiesOutput = Field(..., description="PII mentions present in `text`.")
