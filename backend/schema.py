"""Pydantic schema for the per-request pipeline configuration.

Mirrors `frontend/src/lib/pipelineConfig.schema.ts` (valibot). Keep these two
in lockstep when you add fields. We treat the wire payload defensively —
unknown fields are ignored, malformed fields fall back to safe defaults.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RegexMode = Literal["full", "partial", "exclude"]


class LabelRuleConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    regex: str = ""
    regexMode: RegexMode = "full"
    threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    validateLuhn: bool = False


class CustomLabelConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    displayLabel: str
    color: str = "#888888"
    description: str = ""


class PaddleConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    layoutThreshold: float = Field(default=0.5, ge=0.0, le=1.0)
    useDocOrientationClassify: bool = False
    useDocUnwarping: bool = False
    useTextlineOrientation: bool = False
    useChartRecognition: bool = False
    useSealRecognition: bool = False
    useOcrForImageBlock: bool = False


class GlinerConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    modelName: str | None = None
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    enabledLabels: list[str] = Field(default_factory=list)
    descriptions: dict[str, str] = Field(default_factory=dict)
    rules: dict[str, LabelRuleConfig] = Field(default_factory=dict)
    customLabels: dict[str, CustomLabelConfig] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """Top-level request config. All sections optional — missing = defaults."""

    model_config = ConfigDict(extra="ignore")
    paddleocr: PaddleConfig = Field(default_factory=PaddleConfig)
    gliner: GlinerConfig = Field(default_factory=GlinerConfig)


def parse_config(raw: dict | None) -> PipelineConfig:
    """Lenient parser — never raises; returns defaults on any error."""
    if not raw:
        return PipelineConfig()
    try:
        return PipelineConfig.model_validate(raw)
    except Exception:  # noqa: BLE001
        return PipelineConfig()
