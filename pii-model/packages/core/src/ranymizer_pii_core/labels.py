# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""The Swedish PII label taxonomy — the single source of truth for the workspace.

Every label carries its GDPR sensitivity tier, so the **legal** (Art. 10) vs
**medical** (Art. 9) distinction is explicit and queryable rather than implied.
The synthesizer, trainer and evaluation packages all import these labels; nothing
re-declares them, so the categories can never drift out of sync.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Sensitivity(StrEnum):
    """GDPR sensitivity tier of a PII category — the legal/medical axis, first-class."""

    DIRECT = "direct"  # a direct identifier (Art. 6 personal data)
    CONTEXTUAL = "contextual"  # PII-adjacent, not an identifier (date, url)
    ART9_HEALTH = "art9_health"  # Art. 9 special category — MEDICAL
    ART9_BELIEF = "art9_belief"  # Art. 9 — religion / ethnicity / trade-union
    ART10_CRIMINAL = "art10_criminal"  # Art. 10 — LEGAL (offences & convictions)


class PiiLabel(BaseModel, frozen=True):
    """One PII category the detector can mask."""

    name: str
    sensitivity: Sensitivity
    description: str


LABELS: tuple[PiiLabel, ...] = (
    PiiLabel(
        name="person",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of an individual's name (given name + surname, or initials).",
    ),
    PiiLabel(
        name="email",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of an email address, e.g. firstname.lastname@example.se.",
    ),
    PiiLabel(
        name="phone",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a phone number in Swedish or international format (+46, 070-..., 08-...).",
    ),
    PiiLabel(
        name="address",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a street address: street name + number, postnummer, city.",
    ),
    PiiLabel(
        name="personnummer",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a Swedish personal identity number (YYYYMMDD-XXXX or YYMMDD-XXXX).",
    ),
    PiiLabel(
        name="organisationsnummer",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a Swedish organisation number (XXXXXX-XXXX).",
    ),
    PiiLabel(
        name="bank",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of bank account information: bankgiro, plusgiro, IBAN, BIC, clearing+account.",
    ),
    PiiLabel(
        name="date",
        sensitivity=Sensitivity.CONTEXTUAL,
        description="Suggested mention of a calendar date in Swedish format (2024-05-20, 20 maj 2024, etc).",
    ),
    PiiLabel(
        name="url",
        sensitivity=Sensitivity.CONTEXTUAL,
        description="Suggested mention of a web URL (https://..., www...).",
    ),
    PiiLabel(
        name="health",
        sensitivity=Sensitivity.ART9_HEALTH,
        description="Suggested mention of health information: diagnoses, medication, treatment, disability, sick leave, mental health.",
    ),
    PiiLabel(
        name="religion_ethnicity",
        sensitivity=Sensitivity.ART9_BELIEF,
        description="Suggested mention of religious belief, philosophical conviction, ethnic origin, or trade-union membership.",
    ),
    PiiLabel(
        name="criminal",
        sensitivity=Sensitivity.ART10_CRIMINAL,
        description="Suggested mention of criminal offences or convictions (GDPR Art. 10): misstanke om brott, åtal, fällande dom, eller påföljd såsom böter, fängelse, skyddstillsyn eller villkorlig dom.",
    ),
    PiiLabel(
        name="card_number",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a payment card PAN (primary account number).",
    ),
    PiiLabel(
        name="iban",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a Swedish IBAN (international bank account number).",
    ),
    PiiLabel(
        name="ip_address",
        sensitivity=Sensitivity.CONTEXTUAL,
        description="Suggested mention of an IP address (IPv4 or IPv6).",
    ),
    PiiLabel(
        name="username",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of an account login handle (username).",
    ),
    PiiLabel(
        name="date_of_birth",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a person's date of birth.",
    ),
    # ID-document fields — passports, national ID cards, residence permits. The
    # surname and given names sit on SEPARATE lines on a passport, so they are
    # their own spans here (not nested inside `person`).
    PiiLabel(
        name="first_name",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a person's given name(s) only (Förnamn), without the surname.",
    ),
    PiiLabel(
        name="last_name",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a person's family name / surname only (Efternamn), without given names.",
    ),
    PiiLabel(
        name="passport_number",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a passport or ID-document number (Passnr/Passport No), e.g. two letters then digits like AA2130525.",
    ),
    PiiLabel(
        name="place_of_birth",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of a place of birth (Födelseort) — a city or locality where a person was born.",
    ),
    PiiLabel(
        name="mrz",
        sensitivity=Sensitivity.DIRECT,
        description="Suggested mention of the machine-readable zone (MRZ) of a passport or ID card — the OCR-B lines packed with < fillers.",
    ),
)

LABEL_NAMES: tuple[str, ...] = tuple(label.name for label in LABELS)
LABELS_BY_NAME: dict[str, PiiLabel] = {label.name: label for label in LABELS}
LABEL_DESCRIPTIONS: dict[str, str] = {label.name: label.description for label in LABELS}


def names_with(sensitivity: Sensitivity) -> tuple[str, ...]:
    """Label names in one sensitivity tier (e.g. the medical or the legal ones)."""
    return tuple(label.name for label in LABELS if label.sensitivity is sensitivity)


DIRECT_PII: tuple[str, ...] = names_with(Sensitivity.DIRECT)
MEDICAL: tuple[str, ...] = names_with(Sensitivity.ART9_HEALTH)  # ('health',)
LEGAL: tuple[str, ...] = names_with(Sensitivity.ART10_CRIMINAL)  # ('criminal',)

# PII labels that are single-person identifiers (the belongs_to / person_record identifier set).
PERSON_IDENTIFIER_FIELDS: tuple[str, ...] = (
    "personnummer",
    "email",
    "phone",
    "address",
)
# full person_record field set: name + identifiers.
PERSON_RECORD_FIELDS: tuple[str, ...] = ("name", *PERSON_IDENTIFIER_FIELDS)
