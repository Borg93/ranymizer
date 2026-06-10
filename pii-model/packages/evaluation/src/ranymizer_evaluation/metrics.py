# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""LLM-as-judge data-quality metrics for the Swedish PII synthetic recipe.

These mirror the recipe's own per-row judge rubrics (``swedish_naturalness``,
``seed_grounding``, ``label_completeness``) as DeepEval ``GEval`` metrics, add a
``pii_safety`` metric for the GDPR Art. 9 / Art. 10 single-subject +
no-selection-list rule (``3 kap. 3 §`` dataskyddslagen), and a ``DAGMetric``
quality gate.

Every metric's judge LLM is injected via :func:`build_metrics`, so the user's
local Gemma (wrapped by :class:`ranymizer_evaluation.judge.LocalOpenAIJudge`) does
the judging — never OpenAI. The PII label vocabulary comes from the shared kernel
``ranymizer_pii_core``.

The mapping from a recipe output row to a DeepEval test case is:
    input            seed PII values + the generation task description
    actual_output    the generated Swedish ``text``
    expected_output  ``json.dumps(entities)`` — the {label: [mentions]} dict
    context          one string per non-empty seed PII value (the ground truth)
"""

from __future__ import annotations

import ast
import json
import math
from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from deepeval.metrics import BaseMetric, DAGMetric, GEval
from deepeval.metrics.dag import (
    BinaryJudgementNode,
    DeepAcyclicGraph,
    VerdictNode,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams
from pydantic import BaseModel, computed_field
from ranymizer_pii_core import PERSON_IDENTIFIER_FIELDS

if TYPE_CHECKING:
    from deepeval.models import DeepEvalBaseLLM

__all__ = [
    "SEED_FIELDS",
    "BuiltMetrics",
    "PairingResult",
    "build_metrics",
    "pairing_precision_recall",
    "row_to_test_case",
    "score_row_pairing",
]

# Recipe seed columns, in the order they appear in the generation prompt. Each
# is rendered into the test-case ``context`` (the ground-truth PII the text is
# allowed to use). Dict-valued seeds (company/address) are flattened.
SEED_FIELDS: tuple[str, ...] = (
    "seed_person",
    "seed_email",
    "seed_phone",
    "seed_personnummer",
    "seed_company",
    "seed_address",
    "seed_date",
    "seed_url",
    "seed_health",
    "seed_religion_ethnicity",
    "seed_criminal",
    "seed_card",
    "seed_iban",
    "seed_ip",
    "seed_username",
    "seed_dob",
    # Multi-subject rows carry the *other* people's PII here (a list of per-person
    # dicts). Omitting it made `seed_grounding` flag those subjects as "invented".
    "seed_subjects",
)


def _parse_mapping(value: object) -> dict:
    """Best-effort dict from a value that may be a dict / JSON / Python-repr str."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        for parse in (json.loads, ast.literal_eval):
            try:
                parsed = parse(value)
            except (ValueError, SyntaxError):
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def _parse_sequence(value: object) -> list[dict]:
    """Best-effort ``list[dict]`` from a value that may be a list / JSON /
    Python-repr str / numpy array (parquet round-trips lists as ``ndarray``).

    Non-dict elements are dropped; returns ``[]`` when unparseable.
    """
    raw: object = value
    if isinstance(raw, str) and raw:
        for parse in (json.loads, ast.literal_eval):
            try:
                raw = parse(raw)
            except (ValueError, SyntaxError):
                continue
            break
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        seq: Iterable[object] = raw
    elif hasattr(raw, "__iter__") and not isinstance(raw, (str, bytes, dict)):
        # parquet round-trips lists as a numpy ndarray: iterable, not list/tuple.
        seq = cast("Iterable[object]", raw)
    else:
        return []
    out: list[dict] = []
    for item in seq:
        parsed = _parse_mapping(item)
        if parsed:
            out.append(parsed)
    return out


def _coerce_entities(value: object) -> dict[str, list[str]]:
    """Parse an `entities` cell to ``{label: [mentions]}``, tolerating dict /
    JSON / Python-repr string forms (NDD's on-the-wire form is engine-dependent).
    Non-list values are dropped; returns ``{}`` when unparseable.

    Inlined here (not imported) to keep this package coupled only to
    ``ranymizer_pii_core`` and third-party libs.
    """
    raw = _parse_mapping(value)
    return {
        str(k): [str(m) for m in v]
        for k, v in raw.items()
        if isinstance(v, (list, tuple))
    }


def _append_scalar(value: object, out: list[str]) -> None:
    """Append a single non-empty stringified PII value.

    Skips float NaN (pandas renders a missing seed cell as ``float("nan")``) by
    type, not by its string form — a legitimate value that merely *reads* as
    "nan" (e.g. a username) must stay in the grounding context.
    """
    if isinstance(value, float) and math.isnan(value):
        return
    text = str(value).strip()
    if text:
        out.append(text)


def _container_from_str(value: str) -> object | None:
    """Parse a string that encodes a JSON / Python-repr container, else ``None``.

    Parquet/JSONL round-trips can deliver ``seed_subjects`` (and the dict seeds)
    as their *serialised string* form; treating that blob as one scalar would
    hide every subject's PII from the grounding context.
    """
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{(":
        return None
    for parse in (json.loads, ast.literal_eval):
        try:
            parsed = parse(stripped)
        except (ValueError, SyntaxError):
            continue
        if isinstance(parsed, (dict, list, tuple)):
            return parsed
    return None


def _flatten_seed(value: object, out: list[str]) -> None:
    """Recursively collect scalar PII strings from one seed cell into ``out``.

    Handles scalars, dicts / pydantic models (CompanySeed, address), iterables —
    notably ``seed_subjects`` (a list/ndarray of per-person dicts on
    multi-subject rows) — and their serialised string forms, whose every value
    must count as ground-truth PII. ``str``/``bytes`` are scalars and must be
    checked before the iterable branch.
    """
    if value is None:
        return
    if isinstance(value, BaseModel):
        for sub in value.model_dump().values():
            _flatten_seed(sub, out)
        return
    if isinstance(value, dict):
        for sub in value.values():
            _flatten_seed(sub, out)
        return
    if isinstance(value, bytes):
        _append_scalar(value, out)
        return
    if isinstance(value, str):
        container = _container_from_str(value)
        if container is None:
            _append_scalar(value, out)
            return
        _flatten_seed(container, out)
        return
    if isinstance(value, Iterable):
        for item in cast("Iterable[object]", value):
            _flatten_seed(item, out)
        return
    _append_scalar(value, out)


def _seed_values(row: dict) -> list[str]:
    """Flatten the row's seed columns into a list of ground-truth PII strings."""
    out: list[str] = []
    for field in SEED_FIELDS:
        _flatten_seed(row.get(field), out)
    return out


def row_to_test_case(row: dict) -> LLMTestCase:
    """Map a recipe output row ``{text, entities, seed_*}`` to an LLMTestCase.

    ``entities`` is robustly parsed with :func:`_coerce_entities` (tolerates
    dict / JSON / Python-repr string forms).
    """
    text = str(row.get("text") or "")
    entities = _coerce_entities(row.get("entities"))
    seeds = _seed_values(row)

    seed_block = "\n".join(f"- {value}" for value in seeds) or "(no seed values)"
    task = (
        "Task: write a realistic Swedish PII text fragment that uses only the "
        "seed PII values below, and label every PII mention.\n\n"
        f"Seed PII values (the only allowed PII):\n{seed_block}"
    )

    return LLMTestCase(
        input=task,
        actual_output=text,
        expected_output=json.dumps(entities, ensure_ascii=False),
        context=seeds,
    )


# ── Deterministic belongs_to pairing metric (no LLM) ─────────────────────────
#
# Computable on generated rows *now* (records vs. seed_subjects) and reusable on
# model output later (predicted records vs. the same seed_subjects). A "pair" is
# an ``(identifier_value, owner_name)`` edge: the assertion that one identifier
# belongs to one person. Precision/recall compare the pairs a row's ``records``
# assert against the ground-truth pairs in ``seed_subjects``.


def _norm(value: object) -> str:
    """Normalise a pairing value for comparison (trim + casefold whitespace)."""
    return " ".join(str(value).split()).casefold()


def _pairs_from_subjects(subjects: object) -> set[tuple[str, str, str]]:
    """``(field, normalised identifier, normalised owner)`` edges from a list of
    person bundles (``records`` or ``seed_subjects``).

    Robust to the list arriving as JSON / Python-repr / numpy forms; each bundle
    is a mapping with a ``name`` owner and the
    :data:`~ranymizer_pii_core.PERSON_IDENTIFIER_FIELDS` identifiers.
    """
    pairs: set[tuple[str, str, str]] = set()
    for subject in _parse_sequence(subjects):
        owner = subject.get("name")
        if owner in (None, ""):
            continue
        owner_n = _norm(owner)
        for field in PERSON_IDENTIFIER_FIELDS:
            value = subject.get(field)
            if value in (None, ""):
                continue
            pairs.add((field, _norm(value), owner_n))
    return pairs


def pairing_precision_recall(
    records: object, seed_subjects: object
) -> dict[str, float | int]:
    """Deterministic ``belongs_to`` pairing precision/recall (no LLM).

    Given a row's ``records`` (asserted ``{name, personnummer, email, phone,
    address}`` bundles) and the ground-truth ``seed_subjects`` bundles, build the
    set of ``(identifier -> owner)`` pairs each asserts and compare them:

    - **precision** — of the pairs ``records`` assert, the fraction that match a
      ground-truth seed pair (correctly attributing an identifier to its owner).
    - **recall** — of all ground-truth seed pairs, the fraction that appear
      correctly in ``records``.
    - **f1** — harmonic mean of the two.
    - **pairs_checked** — number of asserted (predicted) pairs considered.

    Both arguments are tolerant of dict / JSON / Python-repr / numpy string
    forms. When ``records`` assert no pairs, precision is 1.0 by convention (no
    wrong assertions); when there are no seed pairs, recall is 1.0.
    """
    predicted = _pairs_from_subjects(records)
    truth = _pairs_from_subjects(seed_subjects)
    correct = predicted & truth

    precision = len(correct) / len(predicted) if predicted else 1.0
    recall = len(correct) / len(truth) if truth else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "pairs_checked": len(predicted),
    }


class PairingResult(BaseModel):
    """Per-row outcome of the deterministic pairing metric (mirrors the per-row
    shape of the LLM metrics so it slots into the same evaluation aggregation).
    """

    precision: float
    recall: float
    f1: float
    pairs_checked: int
    threshold: float

    @computed_field  # type: ignore[prop-decorator]
    @property
    def score(self) -> float:
        """The metric's headline score — the row's pairing F1."""
        return self.f1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        """Whether the row passes (F1 at or above ``threshold``)."""
        return self.f1 >= self.threshold

    def as_dict(self) -> dict[str, float | int | bool]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "pairs_checked": self.pairs_checked,
            "score": self.score,
            "success": self.success,
        }


def score_row_pairing(row: dict, *, threshold: float = 1.0) -> PairingResult:
    """Compute the deterministic pairing metric for one row.

    Reads ``records`` and ``seed_subjects`` from the row (each tolerant of
    JSON/repr/numpy string forms) and returns a :class:`PairingResult`. Default
    ``threshold`` of 1.0 demands every asserted/expected pair be exactly right
    (the F1 == 1.0 gate); lower it to allow partial credit.
    """
    stats = pairing_precision_recall(row.get("records"), row.get("seed_subjects"))
    return PairingResult(
        precision=float(stats["precision"]),
        recall=float(stats["recall"]),
        f1=float(stats["f1"]),
        pairs_checked=int(stats["pairs_checked"]),
        threshold=threshold,
    )


# ── GEval metric definitions (all judge calls use the injected model) ────────


def _swedish_naturalness(model: DeepEvalBaseLLM, threshold: float) -> GEval:
    """Referenceless: is ``actual_output`` natural, idiomatic Swedish?"""
    return GEval(
        name="swedish_naturalness",
        evaluation_steps=[
            "Read 'actual output' as Swedish text and judge only its language "
            "quality, not its content or PII.",
            "Reward text that reads like authentic Swedish written by a native "
            "speaker, with idiomatic phrasing and correct grammar.",
            "Penalise translation-like, stiff, or templated phrasing, English "
            "words used where Swedish exists, and obvious machine-translation "
            "artifacts.",
            "Non-prose layouts (key:value lines, form rows, table rows, bullet "
            "lists) are valid: judge the Swedish in the labels/values, do not "
            "penalise the layout itself.",
            "If the text is not Swedish or is unintelligible, give the lowest score.",
        ],
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
        model=model,
        threshold=threshold,
    )


def _seed_grounding(model: DeepEvalBaseLLM, threshold: float) -> GEval:
    """Reference-based: does ``actual_output`` only use the seed PII in context?"""
    return GEval(
        name="seed_grounding",
        evaluation_steps=[
            "Treat 'context' as the complete list of allowed PII values (the "
            "ground-truth seeds).",
            "Find every PII value mentioned in 'actual output': names, emails, "
            "phone numbers, personnummer, organisationsnummer, bank/giro/IBAN, "
            "addresses, dates, URLs, and any health / religion / ethnicity / "
            "criminal information.",
            "Trivial whitespace or letter-case reformatting of a seed value is "
            "acceptable and should not be penalised.",
            "Heavily penalise any PII value in 'actual output' that does not "
            "correspond to a value in 'context' (an invented or modified PII "
            "value).",
            "Give a high score only when all PII in the text is grounded in the "
            "seeds and nothing is invented.",
        ],
        evaluation_params=[
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.CONTEXT,
        ],
        model=model,
        threshold=threshold,
    )


def _label_completeness(model: DeepEvalBaseLLM, threshold: float) -> GEval:
    """Reference-based: is every PII mention in the text captured in entities?"""
    return GEval(
        name="label_completeness",
        evaluation_steps=[
            "'expected output' is a JSON object mapping PII labels to the list "
            "of mentions that were labeled in the text.",
            "Scan 'actual output' for every PII mention a human reviewer would "
            "want masked (names, emails, phones, personnummer, "
            "organisationsnummer, bank/giro, addresses, dates, URLs, and any "
            "health / religion-ethnicity / criminal information).",
            "Check that each such mention appears verbatim under some label in "
            "'expected output'.",
            "Penalise PII mentions that are visible in the text but missing "
            "from 'expected output'; the more (and the more sensitive) the "
            "misses, the lower the score.",
            "Give the highest score only when every PII mention in the text is "
            "captured in 'expected output'.",
        ],
        evaluation_params=[
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=model,
        threshold=threshold,
    )


def _pii_safety(model: DeepEvalBaseLLM, threshold: float) -> GEval:
    """Referenceless: GDPR Art. 9 / Art. 10 single-subject, no selection lists."""
    return GEval(
        name="pii_safety",
        evaluation_steps=[
            "Identify any GDPR Art. 9 special-category data in 'actual output': "
            "health (diagnosis, medication, treatment, disability, sick leave, "
            "mental health) and religion / philosophical conviction / ethnic "
            "origin / trade-union membership.",
            "Identify any GDPR Art. 10 criminal-offence data: suspicion, "
            "charges, convictions, or penalties (misstanke, åtal, dom, "
            "påföljd, böter, fängelse, skyddstillsyn, villkorlig dom).",
            "A fragment that contains no Art. 9 / Art. 10 data is fully safe "
            "and must get the highest score.",
            "When such data is present, it must concern only ONE individual. "
            "Heavily penalise any text that groups two or more people by a "
            "sensitive attribute or by criminal history (a forbidden "
            "'selection list' under 3 kap. 3 § andra stycket dataskyddslagen, "
            "and Art. 10 GDPR for criminal data).",
            "Give the lowest score to any selection list of people by a "
            "sensitive attribute, regardless of other qualities of the text.",
        ],
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
        model=model,
        threshold=threshold,
    )


def _data_quality_gate(model: DeepEvalBaseLLM, threshold: float) -> DAGMetric:
    """Sequential gate: natural Swedish -> no invented PII -> label completeness.

    The leaf success node defers to the ``label_completeness`` GEval (so a
    passing sample's final score is its labeling quality). Failing the Swedish
    or the invented-PII gate short-circuits to a low score.
    """
    completeness = _label_completeness(model, threshold)

    invents_pii = BinaryJudgementNode(
        criteria=(
            "Does 'actual output' contain any PII value that is NOT present in "
            "'context' (the allowed seed values)? Trivial whitespace/case "
            "reformatting of a seed value does not count as invented."
        ),
        evaluation_params=[
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.CONTEXT,
        ],
        children=[
            VerdictNode(verdict=True, score=2),
            VerdictNode(verdict=False, child=completeness),
        ],
    )

    is_swedish = BinaryJudgementNode(
        criteria="Is 'actual output' natural, fluent Swedish (not a translation, not English)?",
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
        children=[
            VerdictNode(verdict=False, score=0),
            VerdictNode(verdict=True, child=invents_pii),
        ],
    )

    dag = DeepAcyclicGraph(root_nodes=[is_swedish])
    return DAGMetric(
        name="data_quality_gate",
        dag=dag,
        model=model,
        threshold=threshold,
    )


class BuiltMetrics:
    """Container for the constructed metrics, all sharing one judge model."""

    def __init__(
        self,
        swedish_naturalness: GEval,
        seed_grounding: GEval,
        label_completeness: GEval,
        pii_safety: GEval,
        data_quality_gate: DAGMetric,
    ) -> None:
        self.swedish_naturalness = swedish_naturalness
        self.seed_grounding = seed_grounding
        self.label_completeness = label_completeness
        self.pii_safety = pii_safety
        self.data_quality_gate = data_quality_gate

    @property
    def geval_metrics(self) -> list[GEval]:
        """The four standalone GEval metrics (excludes the DAG gate)."""
        return [
            self.swedish_naturalness,
            self.seed_grounding,
            self.label_completeness,
            self.pii_safety,
        ]

    @property
    def all_metrics(self) -> list[BaseMetric]:
        """All metrics (the four GEvals + the DAG gate) as DeepEval BaseMetrics."""
        metrics: list[BaseMetric] = [*self.geval_metrics]
        metrics.append(self.data_quality_gate)
        return metrics


def build_metrics(
    judge_model: DeepEvalBaseLLM,
    *,
    threshold: float = 0.5,
) -> BuiltMetrics:
    """Build all data-quality metrics bound to ``judge_model`` (injectable judge).

    Pass a :class:`ranymizer_evaluation.judge.LocalOpenAIJudge` so the user's local
    Gemma is the judge for every metric.
    """
    return BuiltMetrics(
        swedish_naturalness=_swedish_naturalness(judge_model, threshold),
        seed_grounding=_seed_grounding(judge_model, threshold),
        label_completeness=_label_completeness(judge_model, threshold),
        pii_safety=_pii_safety(judge_model, threshold),
        data_quality_gate=_data_quality_gate(judge_model, threshold),
    )
