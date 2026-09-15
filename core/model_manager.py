import time
import logging
from typing import Any, Dict, List, Optional
import httpx
from config.settings import get_settings

logger = logging.getLogger(__name__)

class ModelManager:
    """Manages interactions with local OpenAI-compatible model endpoints."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.MODEL_BASE_URL
        self.timeout = self.settings.MODEL_TIMEOUT_SECONDS
        
        self.stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
        }

    async def check_health(self) -> bool:
        """Check if the local model server is up."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/models", timeout=5.0)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Model server health check failed: {e}")
            return False

    async def list_available_models(self) -> List[str]:
        """Fetch list of available models from the local server."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/models", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    return [model.get("id", "") for model in data.get("data", [])]
                return []
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def generate_completion(self, model_id: str, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Generate completion using local OpenAI-compatible endpoint."""
        self.stats["total_requests"] += 1
        
        start_time = time.time()
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload
                )
                
                if response.status_code != 200:
                    self.stats["failed_requests"] += 1
                    error_detail = response.text
                    if response.status_code == 404:
                        error_detail = f"Model '{model_id}' might not be downloaded or available locally."
                    logger.error(f"Model server returned status {response.status_code}: {error_detail}")
                    raise ValueError(f"Model server error ({response.status_code}): {error_detail}")
                    
                data = response.json()
                latency = time.time() - start_time
                
                usage = data.get("usage", {})
                self.stats["total_prompt_tokens"] += usage.get("prompt_tokens", 0)
                self.stats["total_completion_tokens"] += usage.get("completion_tokens", 0)
                
                content = data["choices"][0]["message"]["content"]
                
                return {
                    "content": content,
                    "latency": latency,
                    "usage": usage,
                    "model": model_id
                }
        except httpx.RequestError as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Request to model server failed: {e}")
            raise Exception(f"Failed to communicate with local model server: {e}")

model_manager = ModelManager()
