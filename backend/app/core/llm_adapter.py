import asyncio
import instructor
from litellm import completion
from app.core.config import settings
from pydantic import BaseModel
from typing import Type, TypeVar, Optional

T = TypeVar('T', bound=BaseModel)

def sanitize_utf8(text: str) -> str:
    """Sanitizes text by removing invalid surrogate characters to prevent JSON UTF-8 encoding crashes."""
    if not isinstance(text, str):
        return text
    return text.encode('utf-8', 'ignore').decode('utf-8')

class LLMAdapter:
    """Standardized Abstract LLM Adapter using Instructor & LiteLLM.
    Supports dynamic context window size (num_ctx) passed to Ollama via extra_body options."""
    
    def __init__(self):
        self.client = instructor.from_litellm(completion, mode=instructor.Mode.MD_JSON)

    def _sync_create(
        self,
        response_model: Type[T],
        prompt: str,
        system_prompt: str,
        max_retries: int,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> T:
        extra_kwargs = {}
        model_name = settings.LLM_MODEL
        
        clean_prompt = sanitize_utf8(prompt)
        clean_system_prompt = sanitize_utf8(system_prompt)

        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_tok = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
        top_prob = top_p if top_p is not None else settings.LLM_TOP_P

        if settings.LLM_PROVIDER == "openai_compatible" or settings.LLM_PROVIDER == "ollama":
            extra_kwargs["api_base"] = settings.LLM_BASE_URL
            extra_kwargs["api_key"] = settings.LLM_API_KEY or "ollama"
            # Pass num_ctx in extra_body for Ollama to expand context size
            extra_kwargs["extra_body"] = {
                "options": {
                    "num_ctx": settings.LLM_CONTEXT_WINDOW
                }
            }
            if not any(model_name.startswith(p) for p in ["openai/", "ollama/", "ollama_chat/", "gemini/"]):
                model_name = f"openai/{model_name}"
        elif settings.LLM_API_KEY:
            extra_kwargs["api_key"] = settings.LLM_API_KEY

        return self.client.chat.completions.create(
            model=model_name,
            response_model=response_model,
            messages=[
                {"role": "system", "content": clean_system_prompt},
                {"role": "user", "content": clean_prompt}
            ],
            temperature=temp,
            max_tokens=max_tok,
            top_p=top_prob,
            max_retries=max_retries,
            **extra_kwargs
        )

    async def generate_structured(
        self,
        response_model: Type[T],
        prompt: str,
        system_prompt: str = "You are an expert AI assistant.",
        max_retries: int = 3,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> T:
        """Asynchronously executes structured LLM generation in thread pool."""
        return await asyncio.to_thread(
            self._sync_create,
            response_model=response_model,
            prompt=prompt,
            system_prompt=system_prompt,
            max_retries=max_retries,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p
        )

    def _sync_generate_text(
        self,
        prompt: str,
        system_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> str:
        extra_kwargs = {}
        model_name = settings.LLM_MODEL

        clean_prompt = sanitize_utf8(prompt)
        clean_system_prompt = sanitize_utf8(system_prompt)

        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_tok = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
        top_prob = top_p if top_p is not None else settings.LLM_TOP_P

        if settings.LLM_PROVIDER == "openai_compatible" or settings.LLM_PROVIDER == "ollama":
            extra_kwargs["api_base"] = settings.LLM_BASE_URL
            extra_kwargs["api_key"] = settings.LLM_API_KEY or "ollama"
            extra_kwargs["extra_body"] = {
                "options": {
                    "num_ctx": settings.LLM_CONTEXT_WINDOW
                }
            }
            if not any(model_name.startswith(p) for p in ["openai/", "ollama/", "ollama_chat/", "gemini/"]):
                model_name = f"openai/{model_name}"
        elif settings.LLM_API_KEY:
            extra_kwargs["api_key"] = settings.LLM_API_KEY

        response = completion(
            model=model_name,
            messages=[
                {"role": "system", "content": clean_system_prompt},
                {"role": "user", "content": clean_prompt}
            ],
            temperature=temp,
            max_tokens=max_tok,
            top_p=top_prob,
            **extra_kwargs
        )
        msg = response.choices[0].message
        content = msg.content or ""
        # If content is empty (e.g. reasoning model was cut off during thinking), fall back to reasoning
        if not content.strip() and hasattr(msg, "reasoning_content") and msg.reasoning_content:
            content = msg.reasoning_content.strip()

        # Filter em dash per R-02 rules
        content = content.replace("—", "-").replace("–", "-")
        return content.strip()

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "You are an expert AI assistant.",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> str:
        """Asynchronously executes direct raw text generation in thread pool."""
        return await asyncio.to_thread(
            self._sync_generate_text,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p
        )

llm_adapter = LLMAdapter()

