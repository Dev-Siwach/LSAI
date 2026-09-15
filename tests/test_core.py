"""Unit and integration tests for Core engine (Phase 2).

Tests:
1. NetworkMonitor: Air-gap enforcement, socket monkey-patching, event streaming, whitelist.
2. ModelManager: Local endpoint communication, stats tracking, error handling, streaming.
"""

import asyncio
import socket
import unittest
from unittest.mock import patch

import httpx

from core.network_monitor import NetworkMonitor, SecurityException, network_monitor
from core.model_manager import ModelManager, ModelError


class TestNetworkMonitor(unittest.TestCase):
    """Test suite for NetworkMonitor air-gap interceptor."""

    def setUp(self) -> None:
        network_monitor.stop()
        network_monitor.events.clear()
        network_monitor.stats["blocked_requests"] = 0
        network_monitor.stats["allowed_requests"] = 0
        network_monitor.stats["bytes_transferred"] = 0

    def tearDown(self) -> None:
        network_monitor.stop()

    def test_singleton(self) -> None:
        """Verify NetworkMonitor follows singleton pattern."""
        nm2 = NetworkMonitor()
        self.assertIs(nm2, network_monitor)

    def test_start_stop_lifecycle(self) -> None:
        """Verify start patches socket methods and stop restores them."""
        orig_connect = socket.socket.connect
        orig_create = socket.create_connection

        network_monitor.start()
        self.assertTrue(network_monitor._patched)
        self.assertIsNot(socket.socket.connect, orig_connect)
        self.assertIsNot(socket.create_connection, orig_create)

        network_monitor.stop()
        self.assertFalse(network_monitor._patched)
        self.assertIs(socket.socket.connect, orig_connect)
        self.assertIs(socket.create_connection, orig_create)

    def test_whitelist_allowed(self) -> None:
        """Verify whitelisted local hosts and unix sockets pass is_allowed."""
        self.assertTrue(network_monitor.is_allowed("127.0.0.1"))
        self.assertTrue(network_monitor.is_allowed("127.0.0.53"))
        self.assertTrue(network_monitor.is_allowed("127.1.2.3"))
        self.assertTrue(network_monitor.is_allowed("localhost"))
        self.assertTrue(network_monitor.is_allowed("::1"))
        self.assertTrue(network_monitor.is_allowed("0.0.0.0"))
        self.assertTrue(network_monitor.is_allowed("/var/run/docker.sock"))
        self.assertTrue(network_monitor.is_allowed("\x00abstract_sock"))

    def test_external_blocked(self) -> None:
        """Verify external IPs and domain names are rejected by is_allowed."""
        self.assertFalse(network_monitor.is_allowed("8.8.8.8"))
        self.assertFalse(network_monitor.is_allowed("1.1.1.1"))
        self.assertFalse(network_monitor.is_allowed("google.com"))
        self.assertFalse(network_monitor.is_allowed("192.168.1.1"))
        self.assertFalse(network_monitor.is_allowed("10.0.0.1"))

    def test_socket_connect_blocks_external_ip(self) -> None:
        """Verify socket.connect to external destination raises SecurityException."""
        network_monitor.start()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with self.assertRaises(SecurityException) as ctx:
                sock.connect(("8.8.8.8", 53))
            self.assertIn("Air-gap violation", str(ctx.exception))
            self.assertIn("8.8.8.8:53", str(ctx.exception))
        finally:
            sock.close()

        # Check telemetry event recorded
        self.assertEqual(network_monitor.stats["blocked_requests"], 1)
        self.assertEqual(len(network_monitor.events), 1)
        event = network_monitor.events[-1]
        self.assertEqual(event["destination"], "8.8.8.8")
        self.assertEqual(event["port"], 53)
        self.assertEqual(event["status"], "BLOCKED")

    def test_create_connection_blocks_external_domain(self) -> None:
        """Verify socket.create_connection to external host raises SecurityException."""
        network_monitor.start()
        with self.assertRaises(SecurityException):
            socket.create_connection(("example.com", 80))

        self.assertEqual(network_monitor.stats["blocked_requests"], 1)
        event = network_monitor.events[-1]
        self.assertEqual(event["destination"], "example.com")
        self.assertEqual(event["status"], "BLOCKED")

    def test_socket_connect_allows_localhost(self) -> None:
        """Verify socket.connect to 127.0.0.1 records ALLOWED and attempts connection."""
        network_monitor.start()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Port 59999 is unlikely to be listening, expecting ConnectionRefusedError
            # but crucially NOT SecurityException
            sock.connect(("127.0.0.1", 59999))
        except ConnectionRefusedError:
            pass
        except OSError:
            pass
        finally:
            sock.close()

        self.assertEqual(network_monitor.stats["allowed_requests"], 1)
        event = network_monitor.events[-1]
        self.assertEqual(event["destination"], "127.0.0.1")
        self.assertEqual(event["status"], "ALLOWED")

    def test_event_subscriber_broadcast(self) -> None:
        """Verify async subscriber queue receives broadcast event."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run_subscriber_test():
            queue = await network_monitor.subscribe()
            try:
                network_monitor.record_event("test.dest", 9000, "BLOCKED", 0)
                event = queue.get_nowait()
                self.assertEqual(event["destination"], "test.dest")
                self.assertEqual(event["port"], 9000)
                self.assertEqual(event["status"], "BLOCKED")
            finally:
                network_monitor.unsubscribe(queue)

        loop.run_until_complete(run_subscriber_test())
        loop.close()


class TestModelManager(unittest.IsolatedAsyncioTestCase):
    """Test suite for ModelManager local OpenAI-compatible client."""

    async def asyncSetUp(self) -> None:
        self.manager = ModelManager()

    async def asyncTearDown(self) -> None:
        await self.manager.close()

    async def test_initialization(self) -> None:
        """Verify initial state and statistics."""
        self.assertEqual(self.manager.stats["total_requests"], 0)
        self.assertEqual(self.manager.stats["failed_requests"], 0)
        self.assertIn("11434", self.manager.base_url)

    async def test_check_health_success(self) -> None:
        """Verify check_health returns True on 200 response."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": []})

        transport = httpx.MockTransport(handler)
        self.manager._client = httpx.AsyncClient(base_url=self.manager.base_url, transport=transport)

        healthy = await self.manager.check_health()
        self.assertTrue(healthy)

    async def test_check_health_unreachable(self) -> None:
        """Verify check_health returns False when server is down."""
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        self.manager._client = httpx.AsyncClient(base_url=self.manager.base_url, transport=transport)

        healthy = await self.manager.check_health()
        self.assertFalse(healthy)

    async def test_list_available_models(self) -> None:
        """Verify listing models extracts model IDs."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"data": [{"id": "deepseek-r1:32b"}, {"id": "qwen3.8-27b"}]}
            )

        transport = httpx.MockTransport(handler)
        self.manager._client = httpx.AsyncClient(base_url=self.manager.base_url, transport=transport)

        models = await self.manager.list_available_models()
        self.assertEqual(models, ["deepseek-r1:32b", "qwen3.8-27b"])

    async def test_generate_completion_success(self) -> None:
        """Verify successful chat completion parses content and updates token metrics."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Pipe thickness meets ASME standards."}}],
                    "usage": {"prompt_tokens": 15, "completion_tokens": 8},
                }
            )

        transport = httpx.MockTransport(handler)
        self.manager._client = httpx.AsyncClient(base_url=self.manager.base_url, transport=transport)

        result = await self.manager.generate_completion(
            model_id="qwen3.8-27b",
            messages=[{"role": "user", "content": "Check pipe thickness"}],
            temperature=0.2,
            max_tokens=256,
        )

        self.assertEqual(result["content"], "Pipe thickness meets ASME standards.")
        self.assertEqual(result["model"], "qwen3.8-27b")
        self.assertGreater(result["latency"], 0)
        self.assertEqual(self.manager.stats["total_requests"], 1)
        self.assertEqual(self.manager.stats["failed_requests"], 0)
        self.assertEqual(self.manager.stats["total_prompt_tokens"], 15)
        self.assertEqual(self.manager.stats["total_completion_tokens"], 8)

    async def test_generate_completion_not_found(self) -> None:
        """Verify 404 response raises ModelError with informative pull guidance."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="model not found")

        transport = httpx.MockTransport(handler)
        self.manager._client = httpx.AsyncClient(base_url=self.manager.base_url, transport=transport)

        with self.assertRaises(ModelError) as ctx:
            await self.manager.generate_completion(
                model_id="deepseek-r1:32b",
                messages=[{"role": "user", "content": "Hello"}],
            )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("ollama pull deepseek-r1:32b", str(ctx.exception))
        self.assertEqual(self.manager.stats["failed_requests"], 1)

    async def test_generate_completion_stream(self) -> None:
        """Verify streaming token delivery over SSE chunks."""
        sse_body = (
            b'data: {"choices": [{"delta": {"content": "Calculated "}}]}\n\n'
            b'data: {"choices": [{"delta": {"content": "thickness: 8.5mm"}}]}\n\n'
            b'data: [DONE]\n\n'
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=sse_body)

        transport = httpx.MockTransport(handler)
        self.manager._client = httpx.AsyncClient(base_url=self.manager.base_url, transport=transport)

        tokens = []
        async for chunk in self.manager.generate_completion_stream(
            model_id="qwen3.8-27b",
            messages=[{"role": "user", "content": "Calculate thickness"}],
        ):
            tokens.append(chunk)

        self.assertEqual("".join(tokens), "Calculated thickness: 8.5mm")


if __name__ == "__main__":
    unittest.main()
