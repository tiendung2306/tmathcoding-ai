import instructor
from litellm import completion
from app.core.config import settings
from pydantic import BaseModel
from typing import Type, TypeVar

T = TypeVar('T', bound=BaseModel)

class LLMAdapter:
    """Unified LLM Adapter using Instructor & LiteLLM for Pydantic Structured Outputs."""
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.base_url = settings.LLM_BASE_URL
        self.api_key = settings.LLM_API_KEY
        
        # Patch litellm with Instructor for Pydantic validation
        self.client = instructor.from_litellm(completion)

    async def generate_structured(
        self,
        response_model: Type[T],
        prompt: str,
        system_prompt: str = "You are an expert AI assistant.",
        max_retries: int = 3
    ) -> T:
        """Generates 100% Pydantic-validated JSON output from LLM with automatic retry."""
        try:
            extra_kwargs = {}
            if self.provider == "openai_compatible":
                extra_kwargs["api_base"] = self.base_url
                extra_kwargs["api_key"] = self.api_key

            response = self.client.chat.completions.create(
                model=self.model,
                response_model=response_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_retries=max_retries,
                **extra_kwargs
            )
            return response
        except Exception as e:
            # Fallback to Gemini Cloud if Ollama Local fails
            print(f"[LLM FALLBACK] Primary model {self.model} failed: {e}. Trying Fallback...")
            response = self.client.chat.completions.create(
                model="gemini/gemini-2.5-flash",
                response_model=response_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_retries=2
            )
            return response

llm_adapter = LLMAdapter()
