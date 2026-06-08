# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Swedish PII seed-value generators, backed by Faker's ``sv_SE`` locale.

Why Faker and not hand-curated pools: a PII *detector* must generalise to any
Swedish name / street / city it has never seen, so the training seeds need an
effectively unbounded Swedish vocabulary — not a 28-name list. Faker's ``sv_SE``
provider gives exactly that, and its identifiers are format-valid (Luhn-checked
``personnummer`` via ``ssn``, checksum-valid ``organisationsnummer`` via
``org_id``). Everything stays Swedish: we only ever read Faker's Swedish fields,
never its locale-agnostic ``country`` field.

The ``make_*`` functions are pure helpers (importable for unit tests). The
``gen_seed_*`` functions are NDD-decorated row generators registered as
``CustomColumnConfig`` in the recipe.

Bank account numbers (``bankgiro``) stay hand-rolled: Faker ``sv_SE`` has no
bankgiro provider, and its ``iban`` returns a GB IBAN, which would not be
Swedish data.
"""

from __future__ import annotations

import random

import data_designer.config as dd
from faker import Faker

from .pools import _DOMAINS
from .schema import CompanySeed

FAKER_LOCALE = "sv_SE"
_fake = Faker(FAKER_LOCALE)

# Non-Swedish locales for the `foreign_locale_fraction` of rows: a Swedish PII
# detector must still flag a German name or a UK phone number sitting in an
# otherwise-Swedish document, so we mix these in for `seed_locale == "foreign"`
# rows (personnummer/address stay Swedish — those formats are Sweden-specific).
_FOREIGN_LOCALES = ["en_GB", "de_DE", "fr_FR", "ar_AA", "fa_IR", "fi_FI", "pl_PL"]


def _fake_for(locale: str) -> Faker:
    """Return a *fresh* ``Faker`` for ``locale``.

    The module-level ``_fake`` is shared mutable state; NDD dispatches custom
    generators concurrently across an async task queue, so the new generators
    build their own per-call instance to stay thread-safe and reproducible
    instead of racing on the shared singleton.
    """
    return Faker(locale)


def seed_faker(seed: int) -> None:
    """Seed Faker + stdlib ``random`` for reproducible seed generation.

    Note: NDD dispatches custom generators per cell across an async task queue,
    so this pins the *value distribution*, not the exact row order. For a fully
    bit-reproducible dataset, also fix NDD's own sampling seed.
    """
    Faker.seed(seed)
    random.seed(seed)


def faker_version() -> str:
    """Faker version string, recorded in the dataset card for provenance."""
    import faker

    return faker.VERSION


# =============================================================================
# Pure helpers (Swedish, Faker-backed)
# =============================================================================


def _full_name(locale: str | None = None) -> str:
    """Full name from ``locale`` (a fresh per-call Faker), default Swedish.

    Passing a ``locale`` is how ``seed_locale == "foreign"`` rows get a
    non-Swedish name; with no ``locale`` we use the shared ``sv_SE`` singleton
    for back-compat.
    """
    fake = _fake if locale is None else _fake_for(locale)
    return f"{fake.first_name()} {fake.last_name()}"


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
    """Luhn check digit over the 9 digits ``YYMMDDSSS`` of a personnummer."""
    s = 0
    for i, ch in enumerate(digits):
        n = int(ch) * (2 if i % 2 == 0 else 1)
        s += n if n < 10 else n - 9
    return str((10 - s % 10) % 10)


def make_personnummer() -> str:
    """12-digit ``YYYYMMDD-XXXX`` personnummer with a valid Luhn check digit.

    Complements Faker's 10-digit ``ssn`` so the model sees both the
    century-prefixed and short forms (the adversarial eval set in PLAN.md §5
    calls these out explicitly).
    """
    year = random.randint(1940, 2010)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    serial = random.randint(0, 999)
    body = f"{year:04d}{month:02d}{day:02d}{serial:03d}"
    check = _luhn_check_digit(body[2:])  # Luhn is over the last 9 (YYMMDDSSS)
    return f"{year:04d}{month:02d}{day:02d}-{serial:03d}{check}"


def make_personnummer_any() -> str:
    """Pick a personnummer surface form: Faker's 10-digit or our 12-digit."""
    return (
        _fake_for(FAKER_LOCALE).ssn()
        if random.random() < 0.6
        else make_personnummer()
    )


def make_orgnummer() -> str:
    """Valid Swedish organisationsnummer (Faker ``sv_SE``, correct checksum)."""
    return _fake_for(FAKER_LOCALE).org_id()


def make_bankgiro() -> str:
    """Random bankgiro ``NNN-NNNN`` or ``NNNN-NNNN`` (no Faker provider exists)."""
    if random.random() < 0.5:
        return f"{random.randint(100, 999)}-{random.randint(1000, 9999)}"
    return f"{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"


def _format_postnr(postcode: str) -> str:
    """Render a Swedish postnummer as ``NNN NN`` (Faker emits 5 bare digits)."""
    digits = "".join(ch for ch in postcode if ch.isdigit())
    return f"{digits[:3]} {digits[3:]}" if len(digits) == 5 else postcode


def make_address() -> dict[str, str]:
    """Swedish address dict with keys ``street_line``, ``postnr``, ``city``, ``full``."""
    fake = _fake_for(FAKER_LOCALE)
    street_line = f"{fake.street_name()} {fake.building_number()}"
    city = fake.city()
    postnr = _format_postnr(fake.postcode())
    return {
        "street_line": street_line,
        "postnr": postnr,
        "city": city,
        "full": f"{street_line}, {postnr} {city}",
    }


def make_phone(locale: str | None = None) -> str:
    """Phone number from ``locale`` (fresh per-call Faker), default Swedish.

    Swedish ``sv_SE`` mixes +46, 0NN-, and mobile forms; a ``foreign`` locale
    yields that country's own dialling format.
    """
    return _fake_for(locale or FAKER_LOCALE).phone_number()


def make_card_number() -> str:
    """Credit-card number (Luhn-valid, Faker ``credit_card_number``)."""
    return _fake_for(FAKER_LOCALE).credit_card_number()


def make_ip() -> str:
    """Public IPv4 address (Faker ``ipv4_public``)."""
    return _fake_for(FAKER_LOCALE).ipv4_public()


def make_username() -> str:
    """Login / handle username (Faker ``user_name``)."""
    return _fake_for(FAKER_LOCALE).user_name()


def make_dob() -> str:
    """Adult date of birth as ISO ``YYYY-MM-DD`` (ages 18-90)."""
    return (
        _fake_for(FAKER_LOCALE)
        .date_of_birth(minimum_age=18, maximum_age=90)
        .isoformat()
    )


def make_iban_se() -> str:
    """Format- and checksum-valid Swedish IBAN ``SE`` + 2 check digits + 20 BBAN.

    Mod-97 (ISO 13616): move the country code + ``00`` placeholder to the end,
    map letters to digits (S=28, E=14), then ``check = 98 - (rearranged % 97)``.
    Faker ``sv_SE``'s ``iban`` returns a GB IBAN, so we build it by hand.
    """
    bban = "".join(str(random.randint(0, 9)) for _ in range(20))
    # Rearranged string with "SE00" appended: S->28, E->14, "00" placeholder.
    rearranged = bban + "2814" + "00"
    check = 98 - (int(rearranged) % 97)
    return f"SE{check:02d}{bban}"


def make_company() -> dict[str, str]:
    """Company seed dict with keys ``name``, ``org_nr``, ``bankgiro``."""
    return CompanySeed(
        name=_fake_for(FAKER_LOCALE).company(),
        org_nr=make_orgnummer(),
        bankgiro=make_bankgiro(),
    ).model_dump()


def make_subject(locale: str | None = None) -> dict[str, str]:
    """One person bundled with their OWN identifiers — name<->id pairing is ground-truth.

    For a ``foreign`` ``locale`` the name and phone are drawn from that locale;
    personnummer and address stay Swedish because those formats are
    Sweden-specific.
    """
    name = _full_name(locale)
    return {
        "name": name,
        "personnummer": make_personnummer_any(),
        "email": _email_from_name(name),
        "phone": make_phone(locale),
        "address": make_address()["full"],
    }


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


def _row_locale(row: dict) -> str | None:
    """Resolve a row's name/phone Faker locale from its ``seed_locale`` column.

    ``"foreign"`` draws a random non-Swedish locale; anything else (incl. the
    default ``"sv_SE"`` and a missing column) stays Swedish (``None``).
    """
    if row.get("seed_locale") == "foreign":
        return random.choice(_FOREIGN_LOCALES)
    return None


@dd.custom_column_generator(required_columns=["text_type", "seed_locale"])
def gen_seed_person(row: dict) -> dict:
    row["seed_person"] = _full_name(_row_locale(row))
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
    row["seed_personnummer"] = make_personnummer_any()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_company(row: dict) -> dict:
    row["seed_company"] = make_company()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_address(row: dict) -> dict:
    row["seed_address"] = make_address()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_card(row: dict) -> dict:
    row["seed_card"] = make_card_number()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_iban(row: dict) -> dict:
    row["seed_iban"] = make_iban_se()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_ip(row: dict) -> dict:
    row["seed_ip"] = make_ip()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_username(row: dict) -> dict:
    row["seed_username"] = make_username()
    return row


@dd.custom_column_generator(required_columns=["text_type"])
def gen_seed_dob(row: dict) -> dict:
    row["seed_dob"] = make_dob()
    return row


@dd.custom_column_generator(required_columns=["num_subjects", "seed_locale"])
def gen_seed_subjects(row: dict) -> dict:
    locale = _row_locale(row)
    row["seed_subjects"] = [
        make_subject(locale) for _ in range(int(row["num_subjects"]))
    ]
    return row
