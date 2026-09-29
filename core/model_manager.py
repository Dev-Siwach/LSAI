"""Local model manager for OpenAI-compatible endpoints (Ollama / llama-server).

Provides health checks, completion generation (blocking and streaming),
latency tracking, and token statistics — all over localhost only.
"""

import asyncio
import json
import logging
import re
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

        self._resolved_cache: Dict[str, str] = {}
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

    async def resolve_model_id(self, canonical_id: str) -> str:
        """Resolve a canonical model ID (e.g. 'deepseek-r1:32b') to an installed local model tag."""
        if not canonical_id:
            return canonical_id

        if canonical_id in self._resolved_cache:
            return self._resolved_cache[canonical_id]

        available = await self.list_available_models()
        if not available:
            return canonical_id

        # 1. Exact match
        if canonical_id in available:
            self._resolved_cache[canonical_id] = canonical_id
            return canonical_id

        # 2. Match with :latest suffix or case-insensitive
        if f"{canonical_id}:latest" in available:
            self._resolved_cache[canonical_id] = f"{canonical_id}:latest"
            return f"{canonical_id}:latest"

        for m in available:
            if m.lower() == canonical_id.lower() or m.lower() == f"{canonical_id.lower()}:latest":
                self._resolved_cache[canonical_id] = m
                return m

        # 3. Match by token constituents (e.g. 'deepseek-r1:32b' -> 'deepseek', 'r1', '32b')
        parts = [p.lower() for p in re.split(r'[:\-_.]', canonical_id) if p]
        for m in available:
            m_lower = m.lower()
            if all(p in m_lower for p in parts):
                logger.info(f"Resolved canonical model '{canonical_id}' to installed tag '{m}'")
                self._resolved_cache[canonical_id] = m
                return m

        # 4. Family and size fallback (e.g. 'qwen2-vl', '7b' or 'deepseek', '32b')
        for m in available:
            m_lower = m.lower()
            families = ["deepseek", "qwen2-vl", "qwen3", "qwen2.5", "qwen", "gemma"]
            matched_family = next((f for f in families if f in canonical_id.lower()), None)
            if matched_family and matched_family.replace("-", "") in m_lower.replace("-", ""):
                sizes = ["70b", "32b", "27b", "14b", "8b", "7b", "3b", "2b", "1.5b"]
                target_size = next((s for s in sizes if s in canonical_id.lower()), None)
                if not target_size or target_size in m_lower:
                    logger.info(f"Fuzzy-resolved model '{canonical_id}' to '{m}'")
                    self._resolved_cache[canonical_id] = m
                    return m

        return canonical_id

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
        resolved_id = await self.resolve_model_id(model_id)

        start_time = time.time()
        payload: Dict[str, Any] = {
            "model": resolved_id,
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
                        f"Model '{model_id}' (resolved as '{resolved_id}') might not be downloaded or available locally. "
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
        resolved_id = await self.resolve_model_id(model_id)

        payload: Dict[str, Any] = {
            "model": resolved_id,
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
