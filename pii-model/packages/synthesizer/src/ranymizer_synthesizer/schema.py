# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Pydantic generation-output models for the Swedish PII synthesizer.

These are *generation* concerns (the JSON shape the LLM must emit), not the core
taxonomy — the label vocabulary itself lives in ``ranymizer_pii_core``. The
fields of :class:`EntitiesOutput` mirror ``LABEL_NAMES`` from core one-for-one;
a guard at import time fails fast if the two ever drift apart.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from ranymizer_pii_core import LABEL_NAMES, PERSON_RECORD_FIELDS


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
    criminal: list[str] = Field(default_factory=list)
    card_number: list[str] = Field(default_factory=list)
    iban: list[str] = Field(default_factory=list)
    ip_address: list[str] = Field(default_factory=list)
    username: list[str] = Field(default_factory=list)
    date_of_birth: list[str] = Field(default_factory=list)


# Fail fast if the generation schema and the core taxonomy ever drift apart.
if tuple(EntitiesOutput.model_fields) != tuple(LABEL_NAMES):
    raise RuntimeError(
        "EntitiesOutput fields must match ranymizer_pii_core.LABEL_NAMES "
        f"(schema={tuple(EntitiesOutput.model_fields)!r}, core={tuple(LABEL_NAMES)!r})"
    )


class PersonRecord(BaseModel):
    """One individual + the identifiers that belong to THEM (each verbatim in `text`)."""

    name: str = Field(
        ..., description="The person's full name, exactly as written in text."
    )
    personnummer: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None


# Fail fast if this model's fields ever drift from the core taxonomy.
if tuple(PersonRecord.model_fields) != PERSON_RECORD_FIELDS:
    raise RuntimeError(
        "PersonRecord fields must match ranymizer_pii_core.PERSON_RECORD_FIELDS "
        f"(schema={tuple(PersonRecord.model_fields)!r}, core={PERSON_RECORD_FIELDS!r})"
    )


class TextWithEntities(BaseModel):
    """Top-level LLM output for one row."""

    text: str = Field(..., description="The Swedish text fragment we generated.")
    entities: EntitiesOutput = Field(..., description="PII mentions present in `text`.")
    records: list[PersonRecord] = Field(
        default_factory=list,
        description="One entry per individual mentioned; identifiers grouped under their owner.",
    )
