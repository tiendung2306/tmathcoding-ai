import asyncio
import contextvars
import logging
import math
import re
from dataclasses import dataclass
from typing import Optional, Type, TypeVar

import httpx
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMProfile:
    """Connection settings for one family of LLM calls (default or Code Doctor)."""
    provider: str
    base_url: str
    api_key: str
    model: str
    context_window: int


def default_profile() -> LLMProfile:
    # Read settings on every call: tests and operators may change them at runtime.
    return LLMProfile(settings.LLM_PROVIDER, settings.LLM_BASE_URL, settings.LLM_API_KEY,
                      settings.LLM_MODEL, settings.LLM_CONTEXT_WINDOW)


def doctor_profile() -> LLMProfile:
    """Code Doctor settings; each empty DOCTOR_LLM_* value inherits its LLM_* value."""
    base = default_profile()
    return LLMProfile(
        settings.DOCTOR_LLM_PROVIDER or base.provider,
        settings.DOCTOR_LLM_BASE_URL or base.base_url,
        settings.DOCTOR_LLM_API_KEY or base.api_key,
        settings.DOCTOR_LLM_MODEL or base.model,
        settings.DOCTOR_LLM_CONTEXT_WINDOW or base.context_window,
    )


def is_local_ollama(profile: LLMProfile) -> bool:
    return profile.provider in ('openai_compatible', 'ollama') and (
        'ollama' in profile.base_url or ':11434' in profile.base_url)


_THINK_BLOCK = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Remove inline reasoning that some local models put before the answer."""
    if not text:
        return text
    cleaned = _THINK_BLOCK.sub('', text)
    # An unterminated block means the model ran out of tokens while thinking.
    if re.search(r'<think>', cleaned, re.IGNORECASE):
        cleaned = re.split(r'<think>', cleaned, flags=re.IGNORECASE)[0]
    return cleaned.strip()


_active_profile: contextvars.ContextVar[Optional[LLMProfile]] = contextvars.ContextVar('llm_profile', default=None)


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

    @staticmethod
    def _profile() -> LLMProfile:
        return _active_profile.get() or default_profile()

    async def _complete(self, **kwargs):
        timeout = kwargs.pop('timeout')
        model = kwargs.pop('model')
        profile = self._profile()
        if profile.provider in ('openai_compatible', 'ollama') and not model.startswith(('ollama/', 'ollama_chat/', 'gemini/')):
            model = model.removeprefix('openai/')
            # Each request owns its connection. Cancellation also closes the
            # socket while waiting for response headers.
            async with self._http_client(timeout) as transport:
                async with AsyncOpenAI(
                    base_url=profile.base_url,
                    api_key=profile.api_key or 'ollama',
                    http_client=transport,
                    max_retries=0,
                    timeout=httpx.Timeout(timeout, connect=min(10.0, timeout)),
                ) as sdk:
                    response = await sdk.chat.completions.create(model=model, **kwargs)
                    for choice in response.choices or []:
                        if choice.message is not None and choice.message.content:
                            choice.message.content = strip_reasoning(choice.message.content)
                    return response
        # litellm is only needed for non OpenAI-compatible providers and takes seconds
        # to import, so load it lazily instead of on every process start.
        from litellm import acompletion

        extra = {'timeout': timeout, 'num_retries': 0}
        if profile.provider in ('openai_compatible', 'ollama'):
            extra.update(api_base=profile.base_url, api_key=profile.api_key or 'ollama')
        elif profile.api_key:
            extra['api_key'] = profile.api_key
        return await acompletion(model=model, **kwargs, **extra)

    def _arguments(self, prompt, system_prompt, temperature, max_tokens, top_p, timeout):
        profile = self._profile()
        kwargs = dict(
            model=profile.model,
            messages=[
                {'role': 'system', 'content': sanitize_utf8(system_prompt)},
                {'role': 'user', 'content': sanitize_utf8(prompt)},
            ],
            temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
            max_tokens=max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
            top_p=top_p if top_p is not None else settings.LLM_TOP_P,
            timeout=timeout,
        )
        if profile.provider in ('openai_compatible', 'ollama'):
            kwargs['extra_body'] = {'options': {'num_ctx': profile.context_window}}
        # Keep model-default thinking; no reasoning_effort override.
        return kwargs

    async def generate_structured(
        self, response_model: Type[T], prompt: str,
        system_prompt: str = 'You are an expert AI assistant.', max_retries: int = 3,
        temperature: Optional[float] = None, max_tokens: Optional[int] = None,
        top_p: Optional[float] = None, timeout_seconds: Optional[float] = None,
        reasoning_effort: Optional[str] = None, profile: Optional[LLMProfile] = None,
    ) -> T:
        timeout = self._timeout(timeout_seconds)
        token = _active_profile.set(profile) if profile is not None else None
        try:
            # One deadline includes every Instructor validation retry.
            async with asyncio.timeout(timeout):
                arguments = self._arguments(prompt, system_prompt, temperature, max_tokens, top_p, timeout)
                if reasoning_effort is not None:
                    arguments['reasoning_effort'] = reasoning_effort
                return await self.client.chat.completions.create(
                    response_model=response_model, max_retries=max_retries,
                    **arguments,
                )
        except asyncio.CancelledError:
            logger.info('Structured LLM request cancelled; HTTP connection released')
            raise
        except TimeoutError:
            logger.info('Structured LLM deadline expired; HTTP connection released')
            raise
        finally:
            if token is not None:
                _active_profile.reset(token)

    async def generate_text(
        self, prompt: str, system_prompt: str = 'You are an expert AI assistant.',
        temperature: Optional[float] = None, max_tokens: Optional[int] = None,
        top_p: Optional[float] = None, timeout_seconds: Optional[float] = None,
        reasoning_effort: Optional[str] = None, profile: Optional[LLMProfile] = None,
    ) -> str:
        timeout = self._timeout(timeout_seconds)
        token = _active_profile.set(profile) if profile is not None else None
        try:
            async with asyncio.timeout(timeout):
                arguments = self._arguments(prompt, system_prompt, temperature, max_tokens, top_p, timeout)
                if reasoning_effort is not None:
                    arguments['reasoning_effort'] = reasoning_effort
                response = await self._complete(
                    **arguments
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
        finally:
            if token is not None:
                _active_profile.reset(token)


llm_adapter = LLMAdapter()
