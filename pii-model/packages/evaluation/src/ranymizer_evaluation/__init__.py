# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""DeepEval LLM-as-judge data-quality evaluation for the Swedish-PII recipe.

Import entrypoints from their submodules directly:

    from ranymizer_evaluation.run import evaluate_data
    from ranymizer_evaluation.judge import LocalOpenAIJudge
    from ranymizer_evaluation.metrics import build_metrics

These pull in deepeval / openai (heavy), so importing the package root no longer
forces that. Nothing is re-exported here — callers use submodules, so there is
no package-root API to keep in sync.
"""
