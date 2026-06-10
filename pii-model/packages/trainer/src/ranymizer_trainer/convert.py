# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""
Convert NDD output (parquet) → GLiNER2 `InputExample` JSONL.

Drops rows where `entities_validated` is False, normalises the entities dict,
attaches the same `entity_descriptions` we use at inference, and splits
90/5/5 → train/val/test.

Run:
    pii-model convert --raw-path data/raw/swedish_pii_synthetic
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import random
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from gliner2.training.data import (
    Classification,
    InputExample,
    Relation,
    Structure,
    TrainingDataset,
)
from ranymizer_pii_core import LABEL_DESCRIPTIONS
from ranymizer_pii_core import LABEL_NAMES as LABELS

from .ocr import ocr_noise
from .tasks import (
    coerce_entities,
    derive_belongs_to,
    derive_person_record,
    derive_sensitivity,
)

log = logging.getLogger(__name__)

# Faker provenance recorded in the dataset card. The seed values themselves are
# produced upstream by the synthesizer; this package only records *which* Faker
# locale/version produced them, so it imports faker directly (no synthesizer
# coupling) rather than reaching into the synthesizer package.
FAKER_LOCALE = "sv_SE"


def faker_version() -> str:
    """Faker version string, recorded in the dataset card for provenance."""
    import faker

    return faker.VERSION


# Curated, fabricated sensitive-attribute / low-cardinality seed pools. Mirrored
# here (not imported from the synthesizer) purely so the dataset card can pin
# their sha256 for DPIA citation without coupling the trainer to the synthesizer.
# Keep in sync with the synthesizer's seed pools.
_DATE_POOL = [
    "2024-05-20",
    "2025-01-15",
    "20 maj 2024",
    "15 januari 2025",
    "2024-12-03",
    "3 december 2024",
]

_URL_POOL = [
    "https://www.skatteverket.se",
    "https://swish.nu",
    "https://www.bolagsverket.se",
    "https://min.handelsbanken.se",
    "https://www.fk.se",
]

_HEALTH_POOL = [
    "diabetes typ 2",
    "ADHD",
    "depression",
    "astma",
    "Crohns sjukdom",
    "sjukskriven på heltid",
    "rullstolsburen",
    "Metformin 500 mg",
    "Sertralin 50 mg",
    "fysioterapi 1 gång/vecka",
]

_RELIGION_ETHNICITY_POOL = [
    "medlem i Svenska kyrkan",
    "katolik",
    "muslim",
    "judisk församling",
    "ateist",
    "samiskt ursprung",
    "född i Syrien",
    "talar arabiska som modersmål",
    "medlem i IF Metall",
    "medlem i Kommunal",
]

# GDPR Art. 10 — criminal offences / convictions. Generic, fabricated offence
# phrases (no real cases, no real defendants). Kept curated + hashed for the
# same DPIA-citation reason as the Art. 9 pools.
_CRIMINAL_POOL = [
    "misstänkt för stöld",
    "dömd för misshandel",
    "villkorlig dom",
    "dagsböter 50 om 200 kr",
    "skyddstillsyn",
    "åtalad för rattfylleri",
    "narkotikabrott, ringa",
    "tidigare straffad",
    "pågående förundersökning",
    "frikänd i tingsrätten",
]


def _load_parquets(raw_path: Path) -> pd.DataFrame:
    """NDD writes `parquet-files/*.parquet` under the dataset dir."""
    parquet_dir = raw_path / "parquet-files"
    if not parquet_dir.exists():
        parquet_dir = raw_path
    files = sorted(parquet_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files under {parquet_dir}")
    return pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)


def _clean_entities(text: str, raw_entities: object) -> dict[str, list[str]]:
    """Substring-filtered ``{label: [mentions]}`` from a row's raw entities cell.

    Robust to dict / JSON / Python-repr serialisations of the entities column.
    """
    entities = coerce_entities(raw_entities)
    cleaned: dict[str, list[str]] = {}
    for label in LABELS:
        kept = [m for m in entities.get(label, []) if m and m in text]
        if kept:
            cleaned[label] = kept
    return cleaned


def _coerce_records(value: object) -> list[dict]:
    """Parse a 'records' cell to a list[dict], tolerating dict/JSON/repr/None forms."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            import json

            value = json.loads(value)
        except Exception:
            try:
                import ast

                value = ast.literal_eval(value)
            except Exception:
                return []
    if isinstance(value, dict):
        value = [value]
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def _group_key(row: pd.Series) -> str:
    """Seed-identity key for leakage-safe splitting (stable across runs).

    The split must keep every fragment that mentions the same fabricated person
    together, so the same `person`/`personnummer` never straddles two splits.
    The key is the order-independent set of person *names* + `personnummer`
    values found in the row — drawn from BOTH the entities cell and any paired
    `records`, so multi-subject rows group on all their subjects. Rows with no
    person identity (e.g. `no_pii` rows, or url/date-only fragments) get a unique
    per-row key so they are distributed freely rather than collapsed into one
    giant group.
    """
    text = row.get("text") or ""
    entities = _clean_entities(text, row.get("entities"))
    identity: set[str] = set()
    identity.update(entities.get("person", []))
    identity.update(entities.get("personnummer", []))
    if row.get("records_validated"):
        for rec in _coerce_records(row.get("records")):
            for field in ("name", "personnummer"):
                v = rec.get(field)
                if isinstance(v, str) and v and v in text:
                    identity.add(v)
    if not identity:
        # No shared seed identity → singleton group keyed on the row's text, so
        # near-dup-identical texts (already deduped upstream) can't leak either.
        return "text::" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    return "ids::" + "|".join(sorted(identity))


def _assign_split(
    group_key: str, *, seed: int, train_ratio: float, val_ratio: float
) -> str:
    """Deterministically map a group key to ``"train" | "val" | "test"``.

    Stable + seedable: a sha256 of ``f"{seed}:{group_key}"`` yields a fraction in
    [0, 1) that is bucketed by the cumulative train/val ratios. Identical group
    keys always land in the same split (no group spans splits), independent of
    row order or insertion order.
    """
    digest = hashlib.sha256(f"{seed}:{group_key}".encode()).hexdigest()
    frac = int(digest[:16], 16) / float(1 << 64)
    if frac < train_ratio:
        return "train"
    if frac < train_ratio + val_ratio:
        return "val"
    return "test"


def _token_match(value: str, text: str) -> bool:
    """Boundary-aware verbatim membership of ``value`` in ``text``.

    Replicates ``tasks._token_match`` semantics: ``value`` must appear in ``text``
    with no word character (``\\w``) flanking the match, so a short identifier
    (e.g. a name fragment or a personnummer) does not match inside a longer token.
    This deliberately replaces the bare ``value in text`` substring containment
    used previously in ``_tasks_from_records``.
    """
    if not value:
        return False
    return re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text) is not None


def _tasks_from_records(
    records: list[dict], text: str
) -> tuple[list[Structure] | None, list[Relation] | None]:
    """N person_record structures + N belongs_to relations from paired records.

    Only fields whose value appears as a boundary-aware verbatim match in
    ``text`` are kept (same in-text check as ``tasks._token_match``, not a bare
    ``v in text`` substring test); the ``name`` field anchors each record
    (skipped if absent). Every non-name field becomes a
    ``belongs_to(head=value, tail=name)`` edge — the per-record analogue of the
    single-subject ``derive_belongs_to`` path.
    """
    structures: list[Structure] = []
    relations: list[Relation] = []
    for rec in records:
        fields = {k: v for k, v in rec.items() if v and _token_match(str(v), text)}
        person = fields.get("name")
        if not person:
            continue
        structures.append(Structure("person_record", **fields))
        relations += [
            Relation("belongs_to", head=v, tail=person)
            for k, v in fields.items()
            if k != "name"
        ]
    return (structures or None), (relations or None)


def _densify(entities: dict[str, list[str]]) -> dict[str, list[str]]:
    """Expand sparse entities to the full label taxonomy.

    Present labels keep their mentions; every absent label becomes an explicit
    empty list — a queried-but-absent NEGATIVE. A sparse schema only ever shows
    the model present labels, so it never learns "this label is absent here";
    full fine-tuning then overwrites the base checkpoint's calibration and
    over-predicts rare labels. Densifying restores that signal (and turns no-PII
    rows, which a sparse schema drops from the NER task entirely, into full
    negatives).
    """
    return {label: entities.get(label, []) for label in LABELS}


def _example_from(
    text: str,
    cleaned: dict[str, list[str]],
    seed_company: object,
    records: list[dict] | None = None,
    *,
    dense_labels: bool = False,
) -> InputExample:
    """Assemble the four-task InputExample from already-cleaned entities.

    Carries all four GLiNER2 task families at once — entities (the LLM NER
    labels) plus classification / json_structures / relations DERIVED from the
    same {text, entities} with no extra LLM call. ``cleaned`` mentions MUST
    already be verbatim substrings of ``text`` — true for raw rows and for
    OCR-noised rows (``ocr_noise`` preserves the invariant by construction).
    """
    # classification (sensitivity) — ALWAYS present, so every text row is a valid
    # (>=1 task) example and the model gets `no_sensitive` supervision too.
    classifications = [Classification(**derive_sensitivity(text, cleaned))]

    if records and len(records) > 1:
        # Validated multi-person row — emit one person_record + belongs_to edges
        # per already-paired record (single-subject derive_* path can't pair
        # ownership across multiple subjects, so it's bypassed here).
        structures, relations = _tasks_from_records(records, text)
    else:
        # json_structures — one identity record for single-subject rows (None on
        # multi-person rows, where ownership pairing would be ambiguous).
        record = derive_person_record(text, cleaned, seed_company)
        # Structure(**fields) — `fields=` would be swallowed by **fields and emit
        # a spurious nested {"person_record": {"fields": {...}}} wrapper. Spread.
        structures = [Structure("person_record", **record)] if record else None  # ty: ignore[invalid-argument-type]

        # relations — belongs_to(head=identifier, tail=person), single-subject.
        pairs = derive_belongs_to(text, cleaned)
        relations = [Relation("belongs_to", head=h, tail=t) for h, t in pairs] or None

    ents = _densify(cleaned) if dense_labels else cleaned
    return InputExample(
        text=text,
        entities=ents or None,
        entity_descriptions={k: LABEL_DESCRIPTIONS[k] for k in ents} or None,
        classifications=classifications,
        structures=structures,
        relations=relations,
    )


def _row_to_example(
    row: pd.Series, *, dense_labels: bool = False
) -> InputExample | None:
    """Clean (no-noise) multi-task example for a recipe row, or None if empty.

    All four task families of a row stay in one example, and the row's clean +
    OCR examples are routed by the same group key in ``convert`` (see
    ``_group_key`` / ``_assign_split``), so no person/personnummer leaks across
    train/val/test.
    """
    text = row.get("text")
    if not text:
        return None
    cleaned = _clean_entities(text, row.get("entities"))
    records = (
        _coerce_records(row.get("records")) if row.get("records_validated") else []
    )
    return _example_from(
        text, cleaned, row.get("seed_company"), records, dense_labels=dense_labels
    )


def _ocr_example(
    row: pd.Series, rng: random.Random, rate: float, *, dense_labels: bool = False
) -> InputExample | None:
    """OCR-noised augmentation of a row — clean+noised doubles NER/KIE robustness.

    ``ocr_noise`` re-anchors every mention through its index map, so the noised
    mentions stay verbatim substrings of the noised text even when OCR errors
    land inside the PII (``l→1``, ``O→0``, lost ``å/ä/ö``). ``seed_company`` is
    dropped: its clean name no longer appears verbatim in the noised text, so no
    employer is inferred from a stale match.
    """
    text = row.get("text")
    if not text:
        return None
    cleaned = _clean_entities(text, row.get("entities"))
    noised_text, noised_entities = ocr_noise(text, cleaned, rng, rate=rate)
    return _example_from(noised_text, noised_entities, None, dense_labels=dense_labels)


def _drop_semantic_near_dups(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Drop semantic near-duplicate ``text`` rows via the local embedding endpoint.

    Exact-match dedup misses LLM paraphrases (same scenario, reworded). This
    embeds each row's text and greedily keeps the first of every near-dup
    cluster. Opt-in: the embedding endpoint must be running — if it is not, the
    rows pass through unchanged rather than failing the whole convert.

    Raises:
        ValueError: if ``threshold`` is outside ``[0.5, 1.0]`` — a low cosine
            threshold matches nearly everything and would silently collapse the
            dataset to a handful of rows.
    """
    if not 0.5 <= threshold <= 1.0:
        raise ValueError(f"--dedup-threshold must be in [0.5, 1.0], got {threshold}")
    if "text" not in df.columns or df.empty:
        return df

    from openai import OpenAIError

    from .curate import dedup_texts  # lazy: pulls openai + the :8001 endpoint

    texts = df["text"].astype(str).tolist()
    try:
        keep_mask, result = dedup_texts(texts, threshold=threshold)
    except (OpenAIError, ValueError) as exc:
        # ValueError = malformed endpoint response (wrong-sized batch); same
        # degraded mode as endpoint-down: keep all rows rather than fail convert.
        log.warning(f"  Semantic dedup skipped — embedding endpoint error: {exc}")
        return df
    log.info(
        f"  Semantic dedup @ cos>={threshold}: kept {result.kept} / {result.total} "
        f"(dropped {result.dropped})."
    )
    return df[keep_mask].reset_index(drop=True)


def convert(
    *,
    raw_path: Path,
    out_dir: Path,
    train_ratio: float,
    val_ratio: float,
    seed: int,
    ocr_augment: bool,
    ocr_rate: float,
    ocr_seed: int,
    dedup_threshold: float | None = None,
    dense_labels: bool = True,
) -> None:
    """Convert NDD parquet output into GLiNER2 train/val/test JSONL + dataset card.

    Drops unvalidated rows, derives the four GLiNER2 task families per row,
    optionally appends span-preserving OCR-noised variants, splits, and writes a
    DPIA-citable dataset card.
    """
    df = _load_parquets(raw_path)
    log.info(f"Loaded {len(df)} raw rows from {raw_path}")

    if "entities_validated" in df.columns:
        before = len(df)
        df = df[df["entities_validated"] == True].reset_index(drop=True)  # noqa: E712
        log.info(f"  Kept {len(df)} / {before} rows after entity validation.")

    # NEAR-DUP drop — collapse exact-duplicate `text` rows (keep first occurrence).
    # Cheap exact match only; the generator can re-emit an identical fragment, and
    # a duplicate text leaking across splits would inflate eval scores.
    if "text" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset="text", keep="first").reset_index(drop=True)
        dropped = before - len(df)
        if dropped:
            log.info(f"  Dropped {dropped} exact-duplicate-text rows (near-dup).")

    # SEMANTIC near-dup drop (opt-in) — catches paraphrase clusters the exact
    # match above misses, so an over-sampled scenario can't dominate the splits.
    if dedup_threshold is not None:
        df = _drop_semantic_near_dups(df, dedup_threshold)

    test_ratio = 1.0 - train_ratio - val_ratio

    # LEAKAGE-SAFE GROUP-AWARE SPLIT — assign each row to a split by hashing its
    # seed-identity group key, so the same person/personnummer never spans splits.
    # The clean example and its OCR variant share the row's group key, so they
    # always co-locate in one split.
    buckets: dict[str, list[InputExample]] = {"train": [], "val": [], "test": []}
    rng = random.Random(ocr_seed) if ocr_augment else None
    n_clean = 0
    n_ocr = 0
    for _, row in df.iterrows():
        split = _assign_split(
            _group_key(row),
            seed=seed,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
        )
        ex = _row_to_example(row, dense_labels=dense_labels)
        if ex is not None:
            buckets[split].append(ex)
            n_clean += 1
        if rng is not None:
            ocr_ex = _ocr_example(row, rng, ocr_rate, dense_labels=dense_labels)
            if ocr_ex is not None:
                buckets[split].append(ocr_ex)
                n_ocr += 1
    log.info(f"  Converted to {n_clean} gliner2 InputExamples.")
    if ocr_augment:
        log.info(f"  + {n_ocr} OCR-noised variants (rate={ocr_rate}).")
    if dense_labels:
        log.info(
            f"  Dense labels ON: every example carries all {len(LABELS)} labels "
            "(absent = [] negatives)."
        )

    examples = buckets["train"] + buckets["val"] + buckets["test"]
    task_coverage = {
        "entities": sum(1 for e in examples if e.entities),
        "classification": sum(1 for e in examples if e.classifications),
        "json_structures": sum(1 for e in examples if e.structures),
        "relations": sum(1 for e in examples if e.relations),
    }
    log.info(
        "  Task coverage: " + ", ".join(f"{k}={v}" for k, v in task_coverage.items())
    )

    TrainingDataset(examples).validate(raise_on_error=False)  # report, don't crash
    train = TrainingDataset(buckets["train"])
    val = TrainingDataset(buckets["val"])
    test = TrainingDataset(buckets["test"])
    log.info(
        f"  Group-aware split: train={len(train)} val={len(val)} test={len(test)} "
        f"(ratios {train_ratio:.2f}/{val_ratio:.2f}/{test_ratio:.2f}, seed={seed})."
    )
    train.print_stats()

    out_dir.mkdir(parents=True, exist_ok=True)
    train.save(out_dir / "train.jsonl")
    val.save(out_dir / "val.jsonl")
    test.save(out_dir / "test.jsonl")
    log.info(f"\nWrote {out_dir}/{{train,val,test}}.jsonl")

    card_path = out_dir / "dataset_card.md"
    card_path.write_text(
        _dataset_card(
            raw_path=raw_path,
            n_train=len(train),
            n_val=len(val),
            n_test=len(test),
            seed=seed,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            task_coverage=task_coverage,
            ocr_augment=ocr_augment,
            ocr_rate=ocr_rate,
        ),
        encoding="utf-8",
    )
    log.info(f"Wrote {card_path}")


# =============================================================================
# Provenance / dataset card
# =============================================================================


def _hash_pool(values: list[str]) -> str:
    """Stable short hash of a seed pool (so kommun DPIA can cite it)."""
    blob = json.dumps(list(values), ensure_ascii=False, sort_keys=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _git_rev() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def _dataset_card(
    *,
    raw_path: Path,
    n_train: int,
    n_val: int,
    n_test: int,
    seed: int,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    task_coverage: dict[str, int],
    ocr_augment: bool,
    ocr_rate: float,
) -> str:
    """Generate a dataset card mirroring the IMY/DPIA-relevant facts.

    Kept inline (not a Jinja template) so downstream kommuner can copy this
    file verbatim into their konsekvensbedömning (Art. 35 GDPR).
    """
    pools = {
        "health": _HEALTH_POOL,
        "religion_ethnicity": _RELIGION_ETHNICITY_POOL,
        "criminal": _CRIMINAL_POOL,
        "date": _DATE_POOL,
        "url": _URL_POOL,
    }
    pool_lines = [
        f"  - `{name}` — {len(vals)} entries — sha256[:16] = `{_hash_pool(vals)}`"
        for name, vals in pools.items()
    ]
    label_lines = [f"  - `{lab}` — {LABEL_DESCRIPTIONS[lab]}" for lab in LABELS]
    task_lines = "\n".join(
        [
            f"  - `entities` — {task_coverage['entities']} examples — NER over the {len(LABELS)} PII labels.",
            f"  - `classification` — {task_coverage['classification']} — multi-label `sensitivity` (direct_pii / art9_health / art9_religion_ethnicity / art10_criminal / no_sensitive).",
            f"  - `json_structures` — {task_coverage['json_structures']} — one `person_record` per single-subject fragment.",
            f"  - `relations` — {task_coverage['relations']} — `belongs_to(identifier → person)` for single-subject fragments.",
        ]
    )
    ocr_line = (
        f"Each generated row is emitted twice — the clean text and a "
        f"span-preserving OCR-noised variant (rate={ocr_rate}) mimicking PaddleOCR "
        f"artifacts (l/1, O/0, lost å/ä/ö, whitespace and `|` jitter, line-wraps); "
        f"every entity span stays a verbatim substring "
        f"(`ranymizer_trainer/ocr.py`)."
        if ocr_augment
        else "Not applied (pass `--ocr-augment` to `pii-model convert` to enable)."
    )
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    return f"""\
# Ranymizer Swedish-PII synthetic dataset

Generated: {timestamp}
Source parquet: `{raw_path}`
Recipe revision (git): `{_git_rev()}`
Python: {platform.python_version()}  ({platform.platform()})

## Provenance

100 % synthetic. **No real Swedish citizen data is used at any point.**
Every personally-identifying span is fabricated:

- Names, street addresses, postnummer, cities, phone numbers, company names,
  `personnummer` and `organisationsnummer` are generated procedurally by Faker's
  `{FAKER_LOCALE}` locale (`faker=={faker_version()}`). These are format-valid
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

- Recipe: `ranymizer_synthesizer` (Faker `{FAKER_LOCALE}` seeds + NDD).
- Framework: NeMo Data Designer (`data-designer` PyPI package).
- Seed values: Faker `{FAKER_LOCALE}` (`faker=={faker_version()}`) for names,
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
identifier values are NOT pooled — they come from Faker `{FAKER_LOCALE}`.

{chr(10).join(pool_lines)}

## Labels

{chr(10).join(label_lines)}

## Task families (GLiNER2 multi-task)

Each example carries up to four GLiNER2 task families. Only `entities` is
LLM-generated; `classification` / `json_structures` / `relations` are
deterministic projections of the same generation output (no extra LLM tokens),
so one generation pass yields ~one example per family. Multi-subject fragments
omit the structures/relations tasks (ambiguous ownership) but keep entities +
classification.

{task_lines}

## OCR augmentation

{ocr_line}

## Splits

- train: {n_train} rows
- val:   {n_val} rows
- test:  {n_test} rows
- Split ratios: {train_ratio:.2f} / {val_ratio:.2f} / {test_ratio:.2f}
- Leakage-safe **group-aware** split (seed = {seed}): each row is assigned to a
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
"""
