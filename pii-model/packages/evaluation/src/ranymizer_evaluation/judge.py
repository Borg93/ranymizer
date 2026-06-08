# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""DeepEval judge model backed by a local OpenAI-compatible endpoint.

The recipe is judged by the *user's own* local Gemma (vLLM / Ollama / llama.cpp
behind an OpenAI-compatible ``/v1`` API), not by OpenAI's hosted models. This
wraps that endpoint as a ``DeepEvalBaseLLM`` so every DeepEval metric (GEval,
DAGMetric) routes its judging calls through it.

The judge is configured from a shared-kernel :class:`ranymizer_pii_core.ModelEndpoint`
(the same value object that drives generation), so pointing the judge at a
different server is a one-line change at the call site — never hardcoded here.

DeepEval 4.x calls ``model.generate_with_schema(prompt, schema=SchemaCls)``,
whose default implementation (``DeepEvalBaseLLM.generate_with_schema``) calls
``self.generate(prompt, schema=SchemaCls)`` and only falls back to
``self.generate(prompt)`` if that raises ``TypeError``. So ``generate`` /
``a_generate`` accept an optional ``schema`` and return a parsed pydantic
instance when one is supplied (via the OpenAI structured-output ``parse`` API),
otherwise plain text.
"""

from __future__ import annotations

from typing import Any

from deepeval.models import DeepEvalBaseLLM
from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletionUserMessageParam
from pydantic import BaseModel
from ranymizer_pii_core import ModelEndpoint

__all__ = ["LocalOpenAIJudge"]


class LocalOpenAIJudge(DeepEvalBaseLLM):
    """A DeepEval judge that talks to an OpenAI-compatible endpoint.

    Parameters
    ----------
    endpoint:
        The injected :class:`ranymizer_pii_core.ModelEndpoint`. Its ``base_url``,
        ``model``, ``api_key``, ``temperature`` and ``timeout`` configure the
        OpenAI-compatible client used for judging.
    """

    def __init__(self, endpoint: ModelEndpoint) -> None:
        self.base_url = endpoint.base_url
        self.model_name = endpoint.model
        self._api_key = endpoint.api_key or "not-needed"
        self.temperature = endpoint.temperature
        self.timeout = endpoint.timeout
        # Our own typed handle on the sync client. DeepEvalBaseLLM.__init__ also
        # assigns the load_model() result to self.model (untyped), but we read
        # this attribute instead so the client type is preserved for callers.
        self._client = self._build_client()
        # DeepEvalBaseLLM.__init__ sets self.name and calls load_model().
        super().__init__(model=endpoint.model)

    def _build_client(self) -> OpenAI:
        return OpenAI(
            base_url=self.base_url,
            api_key=self._api_key,
            timeout=self.timeout,
        )

    def _async_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            base_url=self.base_url,
            api_key=self._api_key,
            timeout=self.timeout,
        )

    def load_model(self, *_args: Any, **_kwargs: Any) -> Any:
        """Return the OpenAI-compatible client used for judging.

        Annotated ``-> Any`` to match DeepEval's loose ``self.model`` contract:
        ``DeepEvalBaseLLM.load_model`` is declared ``-> DeepEvalBaseLLM``, but every
        concrete subclass (including DeepEval's own ``GPTModel``) returns a provider
        client object instead, so the declared return type cannot be honoured
        literally. The typed client is exposed via ``self._client``.
        """
        return self._client

    def get_model_name(self) -> str:
        return f"local-openai:{self.model_name}"

    def generate(
        self,
        prompt: str,
        schema: type[BaseModel] | None = None,
        **_kwargs: Any,
    ) -> Any:
        """Synchronously judge ``prompt``.

        When ``schema`` is given, request OpenAI structured output and return a
        parsed pydantic instance; otherwise return the raw text content.
        """
        messages = [ChatCompletionUserMessageParam(role="user", content=prompt)]
        if schema is not None:
            completion = self._client.chat.completions.parse(
                model=self.model_name,
                messages=messages,
                response_format=schema,
                temperature=self.temperature,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is not None:
                return parsed
            # Server returned no parsed object: fall back to raw text so
            # DeepEval can trim+load the JSON itself.
            return completion.choices[0].message.content or ""
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
        )
        return response.choices[0].message.content or ""

    async def a_generate(
        self,
        prompt: str,
        schema: type[BaseModel] | None = None,
        **_kwargs: Any,
    ) -> Any:
        """Asynchronous counterpart of :meth:`generate`."""
        client = self._async_client()
        messages = [ChatCompletionUserMessageParam(role="user", content=prompt)]
        try:
            if schema is not None:
                completion = await client.chat.completions.parse(
                    model=self.model_name,
                    messages=messages,
                    response_format=schema,
                    temperature=self.temperature,
                )
                parsed = completion.choices[0].message.parsed
                if parsed is not None:
                    return parsed
                return completion.choices[0].message.content or ""
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
            )
            return response.choices[0].message.content or ""
        finally:
            await client.close()
