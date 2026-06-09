# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Prompts + LLM-judge rubrics for the Swedish PII recipe.

Two prompt families:
    TEXT_GEN_*  — drives `LLMStructuredColumnConfig("generation")` that
                  writes both the Swedish fragment and the entities dict.
    PII_JUDGE_* — drives `LLMJudgeColumnConfig("pii_quality_judge_result")`
                  for downstream filtering.

Prompt ORDERING is load-bearing. Both user prompts put their large CONSTANT
reference block (labels, layout catalog, output shape, hard rules) FIRST with no
Jinja variables, then the per-row variables (text_type/register/layout + seeds)
in a TASK/data footer at the very end. The constant head renders byte-identically
on every row, so the vLLM server prefix-caches it once instead of re-prefilling
~1.5k tokens per request — measured to be the dominant cost of a 200k-row run.
Do NOT interleave `{{ variables }}` into the constant head, or the cache breaks
at the first one and the saving is lost.
"""

from __future__ import annotations

import data_designer.config as dd

TEXT_GEN_SYSTEM_PROMPT = """\
You write realistic Swedish business/personal text fragments and label every PII span.
You return a single JSON object that obeys the response schema exactly.
NEVER invent PII values: only use the seed values provided in the user prompt.
Every entity mention MUST appear verbatim in the `text` field (same casing, same spacing).

NEVER produce text that groups multiple individuals by a sensitive attribute
(religion, ethnic origin, health condition, sexual orientation, trade-union
membership) or by criminal history. Such "selection lists" are forbidden under
3 kap. 3 § andra stycket dataskyddslagen (and, for criminal data, restricted
under Art. 10 GDPR). Sensitive attributes may only appear in the context of one
individual at a time.
"""


TEXT_GEN_PROMPT = """\
You are about to write ONE Swedish text fragment for the TASK given at the END of
this prompt. Read this reference first; everything here is the same for every
fragment, so the only part that changes per request is the TASK at the bottom.

Labels (the PII categories you may tag):
  person, email, phone, address, personnummer, organisationsnummer, bank, date,
  url, health, religion_ethnicity, criminal, card_number, iban, ip_address,
  username, date_of_birth

Layouts — the TASK names ONE layout to use. The non-prose layouts must read like
the FLATTENED text an OCR engine dumps from a screenshot of a real Swedish form,
table, ID card or bank statement — ragged, label-driven, no connecting sentences.
  prose       → 1-3 narrative Swedish sentences, seeds woven in inline.
  key_value   → 4-7 "Fält: värde" lines exactly as exported from a Swedish form
                (Skatteverket-blankett, kontoutdrag eller ID-kort), ONE field
                per line, no prose around them. Use authentic Swedish field
                labels such as Namn, Personnummer, Adress, Postnummer, Ort,
                Organisationsnummer, Bankgiro, Telefon, E-post, Datum, Kontonr.
                Example (kontoutdrag):
                  "Kontohavare: Sven Andersson\\nPersonnummer: 850315-2384\\nKontonummer: 5050-1055\\nAdress: Storgatan 12\\nPostnummer: 111 22\\nOrt: Stockholm"
  form_row    → 2-4 lines that look like a paper/PDF form field: label on the
                left, value pushed to the right with 2+ spaces between them and
                NO colon. A long value may wrap onto the next (indented) line.
                Example (Skatteverket-blankett):
                  "Namn                 Sven Andersson\\nPersonnummer          850315-2384\\nGatuadress            Storgatan 12\\nPostnr och ort        111 22 Stockholm"
  table_row   → A header line then 2-3 data rows. Separate cells with " | " OR
                with 2+ spaces (pick one and keep it consistent). Each cell
                holds a single value verbatim. If one value is too long for its
                column it may wrap onto the next line, indented under its cell —
                that wrapped fragment must still be a verbatim substring.
                Example (tabellutdrag / kontoutdrag table):
                  "Datum | Mottagare | Personnummer | Bankgiro\\n2024-03-15 | Sven Andersson | 850315-2384 | 5050-1055\\n2024-03-18 | Anna Berg | 920611-4527 | 5050-1055"
  list        → A short bulleted list ("- " or "* ") with one PII fact per bullet.
                Example: "- Patient: Sven Andersson\\n- Diagnos: diabetes typ 2"

Output — return a single JSON object:
  - text:     the fragment you wrote (preserve line breaks exactly).
  - entities: a LIST with one entry per PII label that OCCURS in `text`. Each
              entry is {"label": <one label>, "mentions": [verbatim substrings]}.
              Include ONLY labels that occur — OMIT every label you did not use
              (do not add entries with empty mentions).
  - records:  a list of per-person identifier dicts (the TASK says how many).
              Each field value MUST be a verbatim substring of `text`;
              non-sensitive identifiers only (no health/criminal/religion_ethnicity).

Hard rules:
  1. Write Swedish (not English). Names, street, city stay in their original form.
  2. Every mention must be a verbatim substring of `text` — no rephrasing.
  3. Do not invent new PII values beyond the seeds given in the TASK.
  4. Address: write each person's address on ONE line exactly as given — do NOT
     split it into separate street/Ort lines. The address mention must appear as
     its own verbatim substring under `entities.address` (and verbatim in any
     `records` entry) so it stays matchable.
  5. Sensitive seeds (health, religion/ethnicity, criminal) MUST be woven in when
     the requested text type naturally involves them (journalanteckning, LSS,
     biståndsbeslut, domstolsbeslut, polisanmälan) — surface them, do not skip
     them. Even so, never group more than one person by a sensitive attribute or
     by criminal history: at most ONE individual per fragment may carry a
     sensitive mention.
  6. Phone: include the phone number when a contact or form genre naturally has
     one (e.g. kontaktuppgifter, blankett, anmälan, kallelse).
  7. For non-prose layouts, keep cell/value text minimal: no extra commentary
     between labels, no connecting sentences — only labels, separators and
     values, like raw OCR. A table_row may repeat the same column layout across
     several data rows, and a long value may wrap onto an indented next line;
     in every case each value (and each wrapped fragment) must still be a
     verbatim substring of `text` exactly as required by rule 2.
  8. SEED AFFINITY: weave in EVERY seed the requested text type realistically
     contains — do not leave a relevant seed unused. In particular, never skip
     seed_card, seed_iban, seed_ip, seed_username, seed_dob,
     seed_company.org_nr or seed_company.bankgiro when the text type
     naturally carries them. Concrete genre→seed guidance:
       - A leverantörsfaktura / kontoutdrag (med kortköp) uses
         organisationsnummer + IBAN and/or bankgiro (and a card number for any
         card purchase), plus bank and date.
       - A kortbetalning / kortköp-kvitto / återbetalning / card receipt is
         settled by card, so the card number is REQUIRED: the fragment MUST
         include a line like "Kortnummer: <the card-number seed>" using the seed
         card value verbatim — do NOT invent, truncate or mask the digits — plus
         date and bank/amount.
       - An inloggnings-/kontouppgifter or IT-supportärende (med loggrad) uses
         username + ip_address (and email).
       - An id-kort / körkort / Skatteverket-blankett uses date_of_birth (with
         address and personnummer).
     These seeds still obey rules 2-3: use the seed value verbatim, invent
     nothing beyond the seeds, and skip a seed only when it would be unnatural
     for the requested text type.
  9. If the TASK below asks for NO personal data, rules 4-8 do not apply: the
     text MUST contain zero PII, `entities` MUST be an empty list [], and
     `records` MUST be [].

──────────────────────────────────────────────────────────────────────────────
TASK (the only part that changes per row):
{% if content_kind == "no_pii" %}
Write a single realistic Swedish {{ text_type }} fragment in a {{ register }}
register, using the {{ text_layout }} layout, that contains ZERO personal data —
no names, no personnummer, no addresses, no emails, no phone numbers, no
bank/card/IBAN/IP/username/date-of-birth, nothing that identifies a person. Build
it from impersonal content instead: figures, totals, amounts, product or policy
text, general descriptions, and order/reference numbers that are clearly NOT
personnummer (e.g. order/fakturanummer, artikelnummer, beloppsrader).
`entities` MUST be an empty list [] and `records` MUST be [].
{% else %}
Write a single realistic Swedish {{ text_type }} fragment in a {{ register }}
register, using the {{ text_layout }} layout. The fragment MUST naturally use SOME
of these seed PII values (pick at least 2, at most all):

person:               {{ seed_person }}
email:                {{ seed_email }}
phone:                {{ seed_phone }}
personnummer:         {{ seed_personnummer }}
company name:         {{ seed_company.name }}
organisationsnummer:  {{ seed_company.org_nr }}
bankgiro:             {{ seed_company.bankgiro }}
address (one line):   {{ seed_address.street_line }}
address (postnr):     {{ seed_address.postnr }}
address (city):       {{ seed_address.city }}
date:                 {{ seed_date }}
url:                  {{ seed_url }}
health:               {{ seed_health }}
religion/ethnicity:   {{ seed_religion_ethnicity }}
criminal:             {{ seed_criminal }}
card number:          {{ seed_card }}
iban:                 {{ seed_iban }}
ip address:           {{ seed_ip }}
username:             {{ seed_username }}
date of birth:        {{ seed_dob }}
{% if num_subjects | int > 1 %}
This fragment involves {{ num_subjects }} DIFFERENT people. Use ONLY these subjects, and
never mix one person's identifier with another's:
{% for s in seed_subjects %}
  - {{ s.name }} · {{ s.personnummer }} · {{ s.email }} · {{ s.phone }} · {{ s.address }}
{% endfor %}
Lay them out as a {{ text_layout }} (a table or list — one row/line per person).
Return one `records` entry per person, copying THAT person's fields verbatim from the text.
Do NOT attach any health, criminal, or religion/ethnicity detail to anyone in this fragment.
{% else %}
Return exactly one `records` entry for {{ seed_person }}, listing the identifiers you used
(personnummer/email/phone/address) verbatim. Health/criminal/religion stay out of `records`.
{% endif %}
{% endif %}
"""


PII_JUDGE_SYSTEM_PROMPT = """\
You are a strict reviewer of synthetic Swedish PII training data.
You see one generated text fragment and the label dict that came with it.
You score the pair on Swedish quality, faithfulness to the seed PII values,
and label completeness. Be honest — invented PII and missed mentions are serious defects.
"""

# Constant rubric first (cacheable), the per-row sample (text/entities/seeds) last
# — same prefix-cache rationale as TEXT_GEN_PROMPT above.
PII_JUDGE_PROMPT = """\
Evaluate the synthetic Swedish PII training sample shown at the END of this prompt.

Hard rules:
- Penalise text that is not natural Swedish or reads like a translation.
- Penalise any PII in the text that is not present in <seeds_used>.
- Penalise PII mentions visible in the text but missing from <entities>.

<text>
{{ text }}
</text>

<entities>
{{ entities }}
</entities>

<seeds_used>
person:               {{ seed_person }}
email:                {{ seed_email }}
phone:                {{ seed_phone }}
personnummer:         {{ seed_personnummer }}
company:              {{ seed_company.name }}
organisationsnummer:  {{ seed_company.org_nr }}
bankgiro:             {{ seed_company.bankgiro }}
address:              {{ seed_address.full }}
date:                 {{ seed_date }}
url:                  {{ seed_url }}
health:               {{ seed_health }}
religion_ethnicity:   {{ seed_religion_ethnicity }}
criminal:             {{ seed_criminal }}
</seeds_used>
"""

PII_JUDGE_SCORES = [
    dd.Score(
        name="swedish_naturalness",
        description="How natural and idiomatic the Swedish text reads.",
        options={
            4: "Reads like authentic Swedish written by a native speaker.",
            3: "Natural Swedish with minor stylistic awkwardness.",
            2: "Understandable Swedish with noticeable translation-like or stiff artifacts.",
            1: "Poor Swedish; obvious template or machine-translation tone.",
            0: "Not Swedish or unintelligible.",
        },
    ),
    dd.Score(
        name="seed_grounding",
        description="The text uses the provided seed PII values without inventing new ones.",
        options={
            4: "All PII in the text comes verbatim from the seeds; nothing invented.",
            3: "Uses seed values with only trivial whitespace/case reformatting.",
            2: "Mostly uses seeds but contains 1-2 invented or modified PII values.",
            1: "Several invented PII values not in the seeds.",
            0: "Largely invented PII; ignores the seeds.",
        },
    ),
    dd.Score(
        name="label_completeness",
        description="Every PII mention visible in the text is captured in the entities dict.",
        options={
            4: "Every PII mention in the text is correctly labeled in entities.",
            3: "All major PII labeled; at most one minor mention missed.",
            2: "Multiple PII mentions in the text are missing from entities.",
            1: "Most PII mentions in the text are missing from entities.",
            0: "Entities dict is largely empty or unrelated to the text.",
        },
    ),
]
