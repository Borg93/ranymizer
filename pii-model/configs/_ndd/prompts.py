# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Prompts + LLM-judge rubrics for the Swedish PII recipe.

Two prompt families:
    TEXT_GEN_*  — drives `LLMStructuredColumnConfig("generation")` that
                  writes both the Swedish fragment and the entities dict.
    PII_JUDGE_* — drives `LLMJudgeColumnConfig("pii_quality_judge_result")`
                  for downstream filtering.
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
membership). Such "selection lists" are forbidden under 3 kap. 3 § andra
stycket dataskyddslagen. Sensitive attributes may only appear in the context
of one individual at a time.
"""


# Layout switch — gives the model OCR-realistic non-prose surfaces (form rows,
# table cells, key:value lines) instead of only flowing sentences. Critical
# because real ranymizer inputs are screenshots of Skatteverket forms,
# kontoutdrag tables, and ID cards — not paragraphs.
TEXT_GEN_PROMPT = """\
Write a single realistic Swedish {{ text_type }} fragment in a {{ register }} register.
The fragment MUST naturally use SOME of these seed PII values (pick at least 2, at most all):

person:               {{ seed_person }}
email:                {{ seed_email }}
phone:                {{ seed_phone }}
personnummer:         {{ seed_personnummer }}
company name:         {{ seed_company.name }}
organisationsnummer:  {{ seed_company.org_nr }}
bankgiro:             {{ seed_company.bankgiro }}
address (street):     {{ seed_address.street_line }}
address (postnr):     {{ seed_address.postnr }}
address (city):       {{ seed_address.city }}
date:                 {{ seed_date }}
url:                  {{ seed_url }}
health (optional):    {{ seed_health }}
religion/ethnicity:   {{ seed_religion_ethnicity }}

LAYOUT for this fragment: {{ text_layout }}
  prose       → 1-3 narrative Swedish sentences, seeds woven in inline.
  key_value   → 3-6 "Label: värde" lines, one per line, as in an exported form.
                Example: "Personnummer: 850315-2384\\nAdress: Storgatan 12, 111 22 Stockholm"
  form_row    → 1-3 lines that look like a paper form field: label left-aligned
                with the value separated by 2+ spaces (no colon).
                Example: "Personnummer   850315-2384"
  table_row   → A header line then one or two data lines, columns separated by
                " | " or two tabs. Each cell holds a single value verbatim.
                Example: "Namn | Personnummer | Bankgiro\\nSven Andersson | 850315-2384 | 5050-1055"
  list        → A short bulleted list ("- " or "* ") with one PII fact per bullet.
                Example: "- Patient: Sven Andersson\\n- Diagnos: diabetes typ 2"

Then return a JSON object with:
  - text:     the fragment you wrote (preserve line breaks exactly)
  - entities: a dict mapping every PII label you actually used to the list of
              verbatim mentions in `text`. Labels you didn't use must be `[]`.

Labels:
  person, email, phone, address, personnummer, organisationsnummer, bank, date,
  url, health, religion_ethnicity

Hard rules:
  1. Write Swedish (not English). Names, street, city stay in their original form.
  2. Every mention must be a verbatim substring of `text` — no rephrasing.
  3. Do not invent new PII values beyond the seeds.
  4. Address: you may include any of `street_line`, `postnr`, `city`, or the full address.
     Each one used must appear as its own mention under `entities.address`.
  5. Sensitive seeds (health, religion/ethnicity) are OPTIONAL — use them only when
     the {{ text_type }} naturally calls for them (e.g. journalanteckning,
     biståndsbeslut). Never group multiple people by a sensitive attribute. At
     most ONE individual per fragment may carry a sensitive mention.
  6. For non-prose layouts, keep cell/value text minimal: no extra commentary
     between labels. The label : value : label : value pattern must be obvious.
"""


PII_JUDGE_SYSTEM_PROMPT = """\
You are a strict reviewer of synthetic Swedish PII training data.
You see one generated text fragment and the label dict that came with it.
You score the pair on Swedish quality, faithfulness to the seed PII values,
and label completeness. Be honest — invented PII and missed mentions are serious defects.
"""

PII_JUDGE_PROMPT = """\
Evaluate this synthetic Swedish PII training sample.

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
</seeds_used>

Hard rules:
- Penalise text that is not natural Swedish or reads like a translation.
- Penalise any PII in the text that is not present in <seeds_used>.
- Penalise PII mentions visible in the text but missing from <entities>.
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
