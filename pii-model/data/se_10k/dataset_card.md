# Ranymizer Swedish-PII synthetic dataset

Generated: 2026-06-10T17:40:26+00:00
Source parquet: `/tmp/dryrun10k/raw/dryrun10k`
Recipe revision (git): `9a289db`
Python: 3.12.3  (Linux-6.17.0-1023-oem-x86_64-with-glibc2.39)

## Provenance

100 % synthetic. **No real Swedish citizen data is used at any point.**
Every personally-identifying span is fabricated:

- Names, street addresses, postnummer, cities, phone numbers, company names,
  `personnummer` and `organisationsnummer` are generated procedurally by Faker's
  `sv_SE` locale (`faker==20.1.0`). These are format-valid
  Swedish values (Luhn-checked personnummer, checksum-valid organisationsnummer)
  drawn from an effectively unbounded synthetic vocabulary — never a real
  register. Only Faker's Swedish fields are read; its locale-agnostic `country`
  field is never used, so no foreign person data enters the dataset.
- `bankgiro` is a random fabricated number (Faker has no bankgiro provider).
- Sensitive labels — Art. 9 (`health`, `religion_ethnicity`) and Art. 10
  (`criminal`) — plus the small `date` / `url` pools, come from short
  hand-curated, fabricated phrases: no real medical records, no real
  congregational lists, no real criminal cases. Their exact contents are pinned
  by the sha256 hashes below.

This matches the practice followed by Atea/Lidingö stad in IMY's regulatory
sandbox project IMY-2024-5156, §2.4: *"Deltagarna har uppgett att man endast
har använt fabricerade uppgifter inom ramen för detta projekt för att utvärdera
olika modellers prestanda."*

## Generator

- Recipe: `ranymizer_synthesizer` (Faker `sv_SE` seeds + NDD).
- Framework: NeMo Data Designer (`data-designer` PyPI package).
- Seed values: Faker `sv_SE` (`faker==20.1.0`) for names,
  addresses, phones, companies, `personnummer`, `organisationsnummer`; curated
  pools (below) for sensitive Art. 9 phrases and `date` / `url`.
- LLM: configured per run (see the NDD `model_alias` in
  `pii-model generate` / `pii-model preview`).
- Quality filters applied before this split:
  - Substring validator (`entities_validated == True`): every labelled
    mention must appear verbatim in the generated text.
  - LLM-as-judge rubrics (`swedish_naturalness`, `seed_grounding`,
    `label_completeness`) — see `PII_JUDGE_SCORES` in the recipe.

## Curated seed pools (sha256[:16] for DPIA citation)

These small, hand-curated, fabricated pools are pinned by hash so a kommun DPIA
can cite the exact sensitive-attribute vocabulary used. Person / address /
identifier values are NOT pooled — they come from Faker `sv_SE`.

  - `health` — 10 entries — sha256[:16] = `d122900b23f656b0`
  - `religion_ethnicity` — 10 entries — sha256[:16] = `376ed521185d6ed9`
  - `criminal` — 10 entries — sha256[:16] = `044050080ee06706`
  - `date` — 6 entries — sha256[:16] = `4d5a7f5491f5705d`
  - `url` — 5 entries — sha256[:16] = `0517cdf632c13321`

## Labels

  - `person` — Suggested mention of an individual's name (given name + surname, or initials).
  - `email` — Suggested mention of an email address, e.g. firstname.lastname@example.se.
  - `phone` — Suggested mention of a phone number in Swedish or international format (+46, 070-..., 08-...).
  - `address` — Suggested mention of a street address: street name + number, postnummer, city.
  - `personnummer` — Suggested mention of a Swedish personal identity number (YYYYMMDD-XXXX or YYMMDD-XXXX).
  - `organisationsnummer` — Suggested mention of a Swedish organisation number (XXXXXX-XXXX).
  - `bank` — Suggested mention of bank account information: bankgiro, plusgiro, IBAN, BIC, clearing+account.
  - `date` — Suggested mention of a calendar date in Swedish format (2024-05-20, 20 maj 2024, etc).
  - `url` — Suggested mention of a web URL (https://..., www...).
  - `health` — Suggested mention of health information: diagnoses, medication, treatment, disability, sick leave, mental health.
  - `religion_ethnicity` — Suggested mention of religious belief, philosophical conviction, ethnic origin, or trade-union membership.
  - `criminal` — Suggested mention of criminal offences or convictions (GDPR Art. 10): misstanke om brott, åtal, fällande dom, eller påföljd såsom böter, fängelse, skyddstillsyn eller villkorlig dom.
  - `card_number` — Suggested mention of a payment card PAN (primary account number).
  - `iban` — Suggested mention of a Swedish IBAN (international bank account number).
  - `ip_address` — Suggested mention of an IP address (IPv4 or IPv6).
  - `username` — Suggested mention of an account login handle (username).
  - `date_of_birth` — Suggested mention of a person's date of birth.

## Task families (GLiNER2 multi-task)

Each example carries up to four GLiNER2 task families. Only `entities` is
LLM-generated; `classification` / `json_structures` / `relations` are
deterministic projections of the same generation output (no extra LLM tokens),
so one generation pass yields ~one example per family. Multi-subject fragments
omit the structures/relations tasks (ambiguous ownership) but keep entities +
classification.

  - `entities` — 9138 examples — NER over the 17 PII labels.
  - `classification` — 9889 — multi-label `sensitivity` (direct_pii / art9_health / art9_religion_ethnicity / art10_criminal / no_sensitive).
  - `json_structures` — 9131 — one `person_record` per single-subject fragment.
  - `relations` — 8749 — `belongs_to(identifier → person)` for single-subject fragments.

## OCR augmentation

Not applied (pass `--ocr-augment` to `pii-model convert` to enable).

## Splits

- train: 8854 rows
- val:   522 rows
- test:  513 rows
- Split ratios: 0.90 / 0.05 / 0.05
- Leakage-safe **group-aware** split (seed = 42): each row is assigned to a
  split by hashing its seed-identity group key (the set of `person` names +
  `personnummer` values in the row), so the same fabricated individual — and a
  row's clean + OCR-noised variants — never straddle train/val/test. Exact
  duplicate-`text` rows are dropped before splitting.

## Suggested DPIA references

When a kommun deploys a model trained on this dataset, the relevant Art. 35
GDPR konsekvensbedömning criteria from IMY's förteckning that typically apply
are:

- 4) Behandling av känsliga personuppgifter samt uppgifter om lagöverträdelser
  (labels `health`, `religion_ethnicity` = Art. 9; `criminal` = Art. 10,
  3 kap. 8-9 §§ dataskyddslagen).
- 5) Behandling av personuppgifter i stor omfattning.
- 7) Behandling av personuppgifter om personer i underläge eller
  beroendeställning (text genres `socialtjänstanteckning`, `LSS-utredning`,
  `skolärende`, `biståndsbeslut`, `journalanteckning`).
- 8) Användning av ny teknik / nya organisatoriska lösningar.

Two or more = DPIA required (IMY-2024-5156, §6.3).

## Constraints honoured by the recipe

- 3 kap. 3 § andra stycket dataskyddslagen — `TEXT_GEN_SYSTEM_PROMPT`
  explicitly forbids grouping multiple individuals by a sensitive attribute.
- Art. 5(1)(b) ändamålsprincipen — the dataset is generated solely for the
  purpose of training a PII-detection (masking) model and contains no real
  personal data that could be re-purposed.
