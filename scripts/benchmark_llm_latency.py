"""Read-only latency probes; no source, diagnosis cache or tags are written."""
import asyncio
import json
import time
import sys
import threading
from unittest.mock import AsyncMock, patch

import httpx
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.services.code_doctor_service import CodeDoctorService


async def main(doctor_default_only=False):
    base = settings.LLM_BASE_URL.removesuffix('/v1').rstrip('/')
    async with httpx.AsyncClient(timeout=150) as client:
        version = (await client.get(base + '/api/version')).json()
        print(json.dumps({'version': version, 'model': settings.LLM_MODEL, 'context': settings.LLM_CONTEXT_WINDOW}), flush=True)
        async def probe(label, messages, native=False, no_think=False, limit=32):
            payload = dict(model=settings.LLM_MODEL, messages=messages, stream=False)
            if native:
                payload.update(think=False, options={'num_ctx': settings.LLM_CONTEXT_WINDOW, 'num_predict': limit, 'temperature': 0.2})
            else:
                payload.update(max_tokens=limit, temperature=0.2)
                if no_think:
                    payload['reasoning_effort'] = 'none'
            start = time.perf_counter()
            response = await client.post(base + ('/api/chat' if native else '/v1/chat/completions'), json=payload)
            response.raise_for_status()
            data = response.json()
            message = data.get('message') if native else data['choices'][0]['message']
            print(json.dumps({'label': label, 'seconds': round(time.perf_counter()-start, 3),
                              'content_chars': len(message.get('content') or ''),
                              'reasoning_chars': len(message.get('thinking') or message.get('reasoning') or message.get('reasoning_content') or ''),
                              'finish': data.get('done_reason') if native else data['choices'][0].get('finish_reason'),
                              'usage': data.get('usage'),
                              'load_s': data.get('load_duration', 0)/1e9,
                              'prompt_s': data.get('prompt_eval_duration', 0)/1e9,
                              'generation_s': data.get('eval_duration', 0)/1e9,
                              'prompt_tokens': data.get('prompt_eval_count'), 'output_tokens': data.get('eval_count')}), flush=True)
        small = [{'role': 'user', 'content': 'Reply with exactly OK.'}]
        if not doctor_default_only:
            await probe('small_default', small)
            await probe('small_no_think_v1', small, no_think=True)
            await probe('small_no_think_native', small, native=True)
        async with AsyncSessionLocal() as db:
            with patch('app.services.code_doctor_service.llm_adapter.generate_text', new=AsyncMock(return_value='Read-only latency benchmark captures the existing prompt.')) as capture, patch('app.services.code_doctor_service.cache_set', new=AsyncMock()):
                await CodeDoctorService()._diagnose_submission_core(3286489, db)
            kwargs = capture.call_args.kwargs
        await engine.dispose()
        messages = [{'role': 'system', 'content': kwargs['system_prompt']}, {'role': 'user', 'content': kwargs['prompt']}]
        if doctor_default_only:
            await probe('doctor_v1_default_450', messages, limit=450)
            return
        await probe('doctor_native_no_think_450', messages, native=True, limit=450)
        await probe('doctor_v1_no_think_450', messages, no_think=True, limit=450)


async def cancellation_probe():
    finished = threading.Event()
    def worker():
        time.sleep(0.2)
        finished.set()
    try:
        await asyncio.wait_for(asyncio.to_thread(worker), timeout=0.01)
    except asyncio.TimeoutError:
        pass
    await asyncio.sleep(0.25)
    print(json.dumps({'thread_continued_after_await_timeout': finished.is_set()}))


if __name__ == '__main__':
    asyncio.run(cancellation_probe() if '--cancellation-only' in sys.argv else main('--doctor-default' in sys.argv))
