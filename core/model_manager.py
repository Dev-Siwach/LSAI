"""Local model manager for OpenAI-compatible endpoints (Ollama / llama-server).

Provides health checks, completion generation (blocking and streaming),
latency tracking, and token statistics — all over localhost only.
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from config.settings import get_settings

logger = logging.getLogger(__name__)


class ModelError(Exception):
    """Raised when the local model server returns an error or is unreachable."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class ModelManager:
    """Manages interactions with local OpenAI-compatible model endpoints."""

    def __init__(self) -> None:
        self.settings = get_settings()
        # Ensure trailing slash so relative paths resolve within /v1/
        raw_url = self.settings.MODEL_BASE_URL.rstrip("/")
        self.base_url = raw_url + "/"
        self.timeout = self.settings.MODEL_TIMEOUT_SECONDS

        self.stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
        }

        self._client: Optional[httpx.AsyncClient] = None
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the shared async HTTP client, creating it if needed."""
        if self._client is None or self._client.is_closed:
            async with self._get_lock():
                if self._client is None or self._client.is_closed:
                    self._client = httpx.AsyncClient(
                        base_url=self.base_url,
                        timeout=httpx.Timeout(self.timeout, connect=10.0),
                    )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client. Call on app shutdown."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def check_health(self) -> bool:
        """Check if the local model server is up."""
        try:
            client = await self._get_client()
            response = await client.get("models", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Model server health check failed: {e}")
            return False

    async def list_available_models(self) -> List[str]:
        """Fetch list of available models from the local server."""
        try:
            client = await self._get_client()
            response = await client.get("models", timeout=5.0)
            if response.status_code == 200:
                data = response.json() or {}
                return [model.get("id", "") for model in data.get("data", []) if model.get("id")]
            return []
        except Exception as e:
            logger.debug(f"Failed to list models: {e}")
            return []

    async def generate_completion(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate completion using local OpenAI-compatible endpoint.

        Raises:
            ModelError: If the server returns an error or is unreachable.
        """
        self.stats["total_requests"] += 1

        start_time = time.time()
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            client = await self._get_client()
            response = await client.post("chat/completions", json=payload)

            if response.status_code != 200:
                self.stats["failed_requests"] += 1
                error_detail = response.text
                if response.status_code == 404:
                    error_detail = (
                        f"Model '{model_id}' might not be downloaded or available locally. "
                        f"Try running 'ollama pull {model_id}'. Original error: {response.text}"
                    )
                raise ModelError(
                    f"Model server returned status {response.status_code}: {error_detail}",
                    status_code=response.status_code,
                )

            data = response.json() or {}
            duration_s = time.time() - start_time

            usage = data.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens", 0) or 0
            completion_tokens = usage.get("completion_tokens", 0) or 0

            self.stats["total_prompt_tokens"] += prompt_tokens
            self.stats["total_completion_tokens"] += completion_tokens

            choices = data.get("choices") or []
            if not choices:
                self.stats["failed_requests"] += 1
                raise ModelError("Model server returned no choices in response")

            choice = choices[0] or {}
            content = (choice.get("message") or {}).get("content", "")

            tokens_per_sec = (
                round(completion_tokens / duration_s, 1) if duration_s > 0 else 0.0
            )

            return {
                "content": content,
                "model": data.get("model", model_id),
                "duration_seconds": round(duration_s, 2),
                "latency": duration_s,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "tokens_per_second": tokens_per_sec,
            }

        except ModelError:
            raise
        except httpx.RequestError as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Request to model server failed: {e}")
            raise ModelError(
                f"Failed to connect to local model server at {self.base_url}: {e}"
            )
        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Unexpected error in model completion: {e}")
            raise ModelError(f"Unexpected error communicating with model: {e}")

    async def generate_completion_stream(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream completion tokens from local model server using SSE.

        Raises:
            ModelError: If connection fails or server returns non-200.
        """
        self.stats["total_requests"] += 1

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            client = await self._get_client()
            async with client.stream("POST", "chat/completions", json=payload) as response:
                if response.status_code != 200:
                    self.stats["failed_requests"] += 1
                    body = await response.aread()
                    raise ModelError(
                        f"Model server error ({response.status_code}): {body.decode()}",
                        status_code=response.status_code,
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str) or {}
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices") or []
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        self.stats["total_completion_tokens"] += 1
                        yield content

        except ModelError:
            raise
        except httpx.RequestError as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Streaming request to model server failed: {e}")
            raise ModelError(f"Failed to stream from local model server: {e}")


model_manager = ModelManager()
