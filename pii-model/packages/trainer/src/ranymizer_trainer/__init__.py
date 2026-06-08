# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Turn synthesized parquet into a trained GLiNER2 model.

Import entrypoints from their submodules directly:

    from ranymizer_trainer.convert import convert
    from ranymizer_trainer.train import train
    from ranymizer_trainer.modes import TrainMode
    from ranymizer_trainer.tasks import coerce_entities

``convert`` / ``train`` pull in gliner2 (heavy); the ``tasks`` / ``ocr`` /
``modes`` submodules are gliner2-free, so importing them never costs a torch
import. Nothing is re-exported here — there is no package-root public API to
keep in sync, and submodule imports make the gliner2 boundary explicit.
"""
