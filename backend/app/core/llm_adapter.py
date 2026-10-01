import asyncio
import logging
import math
from typing import Optional, Type, TypeVar

import httpx
import instructor
from litellm import acompletion
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


def sanitize_utf8(text: str) -> str:
    if not isinstance(text, str):
        return text
    return text.encode('utf-8', 'ignore').decode('utf-8')


class LLMAdapter:
    """Async requests with task-scoped HTTP connections and bounded retries."""

    def __init__(self):
        self.client = instructor.from_litellm(
            self._complete, mode=instructor.Mode.MD_JSON, async_client=True
        )

    def _http_client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=min(10.0, timeout)))

    @staticmethod
    def _timeout(timeout_seconds: Optional[float]) -> float:
        timeout = timeout_seconds if timeout_seconds is not None else settings.LLM_REQUEST_TIMEOUT_SECONDS
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('LLM timeout must be a positive finite number')
        return timeout

    async def _complete(self, **kwargs):
        timeout = kwargs.pop('timeout')
        model = kwargs.pop('model')
        if settings.LLM_PROVIDER in ('openai_compatible', 'ollama') and not model.startswith(('ollama/', 'ollama_chat/', 'gemini/')):
            model = model.removeprefix('openai/')
            # Each request owns its connection. Cancellation also closes the
            # socket while waiting for response headers.
            async with self._http_client(timeout) as transport:
                async with AsyncOpenAI(
                    base_url=settings.LLM_BASE_URL,
                    api_key=settings.LLM_API_KEY or 'ollama',
                    http_client=transport,
                    max_retries=0,
                    timeout=httpx.Timeout(timeout, connect=min(10.0, timeout)),
                ) as sdk:
                    return await sdk.chat.completions.create(model=model, **kwargs)
        extra = {'timeout': timeout, 'num_retries': 0}
        if settings.LLM_PROVIDER in ('openai_compatible', 'ollama'):
            extra.update(api_base=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY or 'ollama')
        elif settings.LLM_API_KEY:
            extra['api_key'] = settings.LLM_API_KEY
        return await acompletion(model=model, **kwargs, **extra)

    def _arguments(self, prompt, system_prompt, temperature, max_tokens, top_p, timeout):
        kwargs = dict(
            model=settings.LLM_MODEL,
            messages=[
                {'role': 'system', 'content': sanitize_utf8(system_prompt)},
                {'role': 'user', 'content': sanitize_utf8(prompt)},
            ],
            temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
            max_tokens=max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
            top_p=top_p if top_p is not None else settings.LLM_TOP_P,
            timeout=timeout,
        )
        if settings.LLM_PROVIDER in ('openai_compatible', 'ollama'):
            kwargs['extra_body'] = {'options': {'num_ctx': settings.LLM_CONTEXT_WINDOW}}
        # Keep model-default thinking; no reasoning_effort override.
        return kwargs

    async def generate_structured(
        self, response_model: Type[T], prompt: str,
        system_prompt: str = 'You are an expert AI assistant.', max_retries: int = 3,
        temperature: Optional[float] = None, max_tokens: Optional[int] = None,
        top_p: Optional[float] = None, timeout_seconds: Optional[float] = None,
    ) -> T:
        timeout = self._timeout(timeout_seconds)
        try:
            # One deadline includes every Instructor validation retry.
            async with asyncio.timeout(timeout):
                return await self.client.chat.completions.create(
                    response_model=response_model, max_retries=max_retries,
                    **self._arguments(prompt, system_prompt, temperature, max_tokens, top_p, timeout),
                )
        except asyncio.CancelledError:
            logger.info('Structured LLM request cancelled; HTTP connection released')
            raise
        except TimeoutError:
            logger.info('Structured LLM deadline expired; HTTP connection released')
            raise

    async def generate_text(
        self, prompt: str, system_prompt: str = 'You are an expert AI assistant.',
        temperature: Optional[float] = None, max_tokens: Optional[int] = None,
        top_p: Optional[float] = None, timeout_seconds: Optional[float] = None,
    ) -> str:
        timeout = self._timeout(timeout_seconds)
        try:
            async with asyncio.timeout(timeout):
                response = await self._complete(
                    **self._arguments(prompt, system_prompt, temperature, max_tokens, top_p, timeout)
                )
                if response.choices[0].finish_reason == 'length':
                    raise ValueError('LLM token limit reached before completing the answer')
                content = response.choices[0].message.content or ''
                # Reasoning without a final answer is not a completed diagnosis.
                if not content.strip():
                    raise ValueError('LLM returned no final answer')
                return content.replace('—', '-').replace('–', '-').strip()
        except asyncio.CancelledError:
            logger.info('Text LLM request cancelled; HTTP connection released')
            raise
        except TimeoutError:
            logger.info('Text LLM deadline expired; HTTP connection released')
            raise


llm_adapter = LLMAdapter()
