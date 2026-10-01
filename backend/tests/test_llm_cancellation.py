import asyncio
import json
import unittest
from unittest.mock import patch

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.llm_adapter import LLMAdapter


class Payload(BaseModel):
    value: int


class CancellationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.started = asyncio.Event()
        self.disconnected = asyncio.Event()
        self.handlers = set()

        async def handler(reader, writer):
            self.handlers.add(asyncio.current_task())
            try:
                headers = await reader.readuntil(b'\r\n\r\n')
                length = next(int(line.split(b':', 1)[1]) for line in headers.split(b'\r\n') if line.lower().startswith(b'content-length:'))
                self.payload = json.loads(await reader.readexactly(length))
                self.started.set()
                self.assertEqual(await reader.read(), b'')
                self.disconnected.set()
            except asyncio.IncompleteReadError:
                pass
            finally:
                writer.close()
                await writer.wait_closed()
                self.handlers.discard(asyncio.current_task())

        self.server = await asyncio.start_server(handler, '127.0.0.1', 0)
        port = self.server.sockets[0].getsockname()[1]
        self.patches = [patch.object(settings, 'LLM_BASE_URL', f'http://127.0.0.1:{port}/v1'),
                        patch.object(settings, 'LLM_PROVIDER', 'openai_compatible')]
        for item in self.patches:
            item.start()
        self.adapter = LLMAdapter()

    async def asyncTearDown(self):
        for item in self.patches:
            item.stop()
        self.server.close()
        await self.server.wait_closed()
        for task in list(self.handlers):
            task.cancel()
        await asyncio.gather(*list(self.handlers), return_exceptions=True)

    async def check_cancel(self, structured=False):
        call = self.adapter.generate_structured(Payload, 'test', timeout_seconds=10) if structured else self.adapter.generate_text('test', timeout_seconds=10)
        task = asyncio.create_task(call)
        await asyncio.wait_for(self.started.wait(), 3)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(self.disconnected.wait(), 2)
        self.assertNotIn('reasoning_effort', self.payload)
        self.assertNotIn('think', self.payload)

    async def test_text_cancellation_closes_real_tcp_socket(self):
        await self.check_cancel()

    async def test_structured_cancellation_closes_real_tcp_socket(self):
        await self.check_cancel(structured=True)

    async def test_deadline_closes_socket(self):
        with self.assertRaises(TimeoutError):
            await self.adapter.generate_text('test', timeout_seconds=2.0)
        self.assertTrue(self.started.is_set())
        await asyncio.wait_for(self.disconnected.wait(), 2)

    async def test_outer_service_timeout_closes_socket(self):
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(self.adapter.generate_text('test', timeout_seconds=10), 0.5)
        await asyncio.wait_for(self.disconnected.wait(), 2)


class ResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_includes_validation_retries(self):
        calls = []
        clients = []
        async def handler(request):
            calls.append(request)
            if len(calls) > 1:
                await asyncio.Event().wait()
            return httpx.Response(200, json={
                'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'test',
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'invalid JSON'}, 'finish_reason': 'stop'}],
            })
        adapter = LLMAdapter()
        def transport(timeout):
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            clients.append(client)
            return client
        adapter._http_client = transport
        with self.assertRaises(TimeoutError):
            await adapter.generate_structured(Payload, 'test', max_retries=3, timeout_seconds=0.5)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(client.is_closed for client in clients))

    async def test_invalid_deadlines_are_rejected(self):
        adapter = LLMAdapter()
        for timeout in (0, -1, float('inf'), float('nan')):
            with self.assertRaises(ValueError):
                await adapter.generate_text('test', timeout_seconds=timeout)

    def adapter(self, contents, finish_reason='stop'):
        self.requests = []
        self.transports = []
        iterator = iter(contents)
        async def handler(request):
            self.requests.append(json.loads(request.content))
            return httpx.Response(200, json={
                'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'test',
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': next(iterator), 'reasoning_content': 'private reasoning'}, 'finish_reason': finish_reason}],
            })
        adapter = LLMAdapter()
        def transport(timeout):
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            self.transports.append(client)
            return client
        adapter._http_client = transport
        return adapter

    async def test_structured_output_and_validation_retry(self):
        adapter = self.adapter(['bad json', '{"value":7}'])
        result = await adapter.generate_structured(Payload, 'test', max_retries=2)
        self.assertEqual(result.value, 7)
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(all(client.is_closed for client in self.transports))

    async def test_text_response_closes_connection(self):
        adapter = self.adapter(['Final answer'])
        self.assertEqual(await adapter.generate_text('test'), 'Final answer')
        self.assertTrue(self.transports[0].is_closed)

    async def test_reasoning_is_not_used_as_final_answer(self):
        with self.assertRaisesRegex(ValueError, 'no final answer'):
            await self.adapter(['']).generate_text('test')

    async def test_truncated_answer_is_not_returned_as_completed(self):
        with self.assertRaisesRegex(ValueError, 'token limit'):
            await self.adapter(['An incomplete answer'], finish_reason='length').generate_text('test')

    async def test_transport_error_has_no_automatic_retry(self):
        calls = []
        clients = []
        async def handler(request):
            calls.append(request)
            return httpx.Response(503, json={'error': {'message': 'unavailable'}})
        adapter = LLMAdapter()
        def transport(timeout):
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            clients.append(client)
            return client
        adapter._http_client = transport
        with self.assertRaises(Exception):
            await adapter.generate_text('test')
        self.assertEqual(len(calls), 1)
        self.assertTrue(clients[0].is_closed)
