# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Shared kernel for the Ranymizer Swedish-PII workspace.

The single source of truth every other package depends on: the PII label
taxonomy (with the legal/medical sensitivity axis) and the injectable LLM
endpoint config. This package has no heavy dependencies (pydantic only), so it
imports anywhere.
"""

from __future__ import annotations

from ranymizer_pii_core.endpoint import ModelEndpoint
from ranymizer_pii_core.labels import (
    DIRECT_PII,
    LABEL_DESCRIPTIONS,
    LABEL_NAMES,
    LABELS,
    LABELS_BY_NAME,
    LEGAL,
    MEDICAL,
    PERSON_IDENTIFIER_FIELDS,
    PERSON_RECORD_FIELDS,
    PiiLabel,
    Sensitivity,
    names_with,
)

__all__ = [
    "DIRECT_PII",
    "LABELS",
    "LABELS_BY_NAME",
    "LABEL_DESCRIPTIONS",
    "LABEL_NAMES",
    "LEGAL",
    "MEDICAL",
    "ModelEndpoint",
    "PERSON_IDENTIFIER_FIELDS",
    "PERSON_RECORD_FIELDS",
    "PiiLabel",
    "Sensitivity",
    "names_with",
]
