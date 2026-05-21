# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Label vocabulary + pydantic output models for the Swedish PII recipe.

Labels are phrased as "suggested mention of …" to align with the IMY
human-in-the-loop framing (Slutrapport IMY-2024-5156, §6.4): the masking
tool proposes spans, the handläggare decides.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

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
    # GDPR Art. 9 / dataskyddslag 3 kap. — sensitive personal data.
    "health",
    "religion_ethnicity",
]

LABEL_DESCRIPTIONS = {
    "person": "Suggested mention of an individual's name (given name + surname, or initials).",
    "email": "Suggested mention of an email address, e.g. firstname.lastname@example.se.",
    "phone": "Suggested mention of a phone number in Swedish or international format (+46, 070-..., 08-...).",
    "address": "Suggested mention of a street address: street name + number, postnummer, city.",
    "personnummer": "Suggested mention of a Swedish personal identity number (YYYYMMDD-XXXX or YYMMDD-XXXX).",
    "organisationsnummer": "Suggested mention of a Swedish organisation number (XXXXXX-XXXX).",
    "bank": "Suggested mention of bank account information: bankgiro, plusgiro, IBAN, BIC, clearing+account.",
    "date": "Suggested mention of a calendar date in Swedish format (2024-05-20, 20 maj 2024, etc).",
    "url": "Suggested mention of a web URL (https://..., www...).",
    "health": "Suggested mention of health information: diagnoses, medication, treatment, disability, sick leave, mental health.",
    "religion_ethnicity": "Suggested mention of religious belief, philosophical conviction, ethnic origin, or trade-union membership.",
}


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
    health: list[str] = Field(default_factory=list)
    religion_ethnicity: list[str] = Field(default_factory=list)


class TextWithEntities(BaseModel):
    """Top-level LLM output for one row."""

    text: str = Field(..., description="The Swedish text fragment we generated.")
    entities: EntitiesOutput = Field(..., description="PII mentions present in `text`.")
