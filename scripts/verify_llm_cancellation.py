"""Exercise the real adapter against Ollama without touching application data."""
import asyncio
import json
import time
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.llm_adapter import LLMAdapter


class Answer(BaseModel):
    answer: str


async def main():
    base = settings.LLM_BASE_URL.removesuffix('/v1').rstrip('/')
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(base + '/api/generate', json={'model': settings.LLM_MODEL, 'prompt': '', 'stream': False})
        response.raise_for_status()
    adapter = LLMAdapter()
    prompt = 'Think carefully and explain a complete proof that there are infinitely many prime numbers.'
    print(json.dumps({'started_at': datetime.now(timezone.utc).isoformat(), 'thinking': 'model default unchanged'}), flush=True)
    task = asyncio.create_task(adapter.generate_text(prompt, max_tokens=2048, timeout_seconds=120))
    await asyncio.sleep(3)
    start = time.perf_counter()
    task.cancel()
    try:
        await task
        raise AssertionError('Request completed before cancellation; probe is inconclusive')
    except asyncio.CancelledError:
        print(json.dumps({'text_cancel_seconds': time.perf_counter() - start}), flush=True)
    await asyncio.sleep(1)
    start = time.perf_counter()
    try:
        await adapter.generate_structured(Answer, prompt, max_tokens=2048, timeout_seconds=3)
        raise AssertionError('Request completed before timeout; probe is inconclusive')
    except TimeoutError:
        print(json.dumps({'structured_timeout_seconds': time.perf_counter() - start}), flush=True)
    await asyncio.sleep(1)
    start = time.perf_counter()
    text = await adapter.generate_text('Reply with exactly OK.', max_tokens=256, timeout_seconds=45)
    print(json.dumps({'followup_seconds': time.perf_counter() - start, 'followup_chars': len(text)}), flush=True)
    start = time.perf_counter()
    answer = await adapter.generate_structured(Answer, 'Return JSON with answer set to OK.', max_tokens=512, timeout_seconds=90)
    print(json.dumps({'structured_success_seconds': time.perf_counter() - start, 'answer_valid': answer.answer == 'OK'}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
