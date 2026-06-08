# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Ranymizer Swedish-PII CLI app — thin orchestration over the domain packages.

This package owns NO domain logic. Each ``pii-model`` subcommand is a thin
wrapper that builds the right config + endpoint and calls a function in one of
the workspace packages: ``ranymizer_synthesizer`` (generate), ``ranymizer_trainer``
(convert, train) or ``ranymizer_evaluation`` (evaluate).
"""
