"""Configuration settings for Sovereign On-Premise Agentic AI Workbench.

Complies with strict air-gap and local sovereign execution requirements.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional
import yaml

# Base project root directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Application settings with environment variable override support."""

    def __init__(self) -> None:
        # App identity
        self.APP_NAME: str = os.getenv("APP_NAME", "Sovereign Industrial AI Workbench")
        self.APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
        self.PROBLEM_STATEMENT_ID: str = os.getenv("PROBLEM_STATEMENT_ID", "26117")

        # Directories
        self.BASE_DIR: Path = BASE_DIR
        self.DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(self.BASE_DIR / "data")))
        self.UPLOADS_DIR: Path = Path(os.getenv("UPLOADS_DIR", str(self.DATA_DIR / "uploads")))
        self.DELIVERABLES_DIR: Path = Path(os.getenv("DELIVERABLES_DIR", str(self.DATA_DIR / "deliverables")))
        self.SAMPLES_DIR: Path = Path(os.getenv("SAMPLES_DIR", str(self.DATA_DIR / "samples")))
        self.STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", str(self.BASE_DIR / "storage")))
        self.QDRANT_DIR: Path = Path(os.getenv("QDRANT_DIR", str(self.STORAGE_DIR / "qdrant")))
        self.CONFIG_DIR: Path = self.BASE_DIR / "config"
        self.MODELS_CONFIG_PATH: Path = Path(os.getenv("MODELS_CONFIG_PATH", str(self.CONFIG_DIR / "models.yaml")))

        # Network & Server
        self.HOST: str = os.getenv("HOST", "127.0.0.1")
        self.PORT: int = int(os.getenv("PORT", "8000"))
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

        # Model Server (OpenAI-compatible local server, e.g. Ollama or llama-server)
        self.MODEL_BASE_URL: str = os.getenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1")
        self.MODEL_TIMEOUT_SECONDS: float = float(os.getenv("MODEL_TIMEOUT_SECONDS", "120.0"))
        self.ACTIVE_PROFILE: str = os.getenv("ACTIVE_PROFILE", "laptop_quantized")

        # Air-Gap Enforcement & Network Monitor
        self.AIRGAP_ENFORCE: bool = os.getenv("AIRGAP_ENFORCE", "true").lower() in ("true", "1", "yes")
        allowed_hosts_str = os.getenv("AIRGAP_ALLOWED_HOSTS", "127.0.0.1,localhost,::1")
        self.AIRGAP_ALLOWED_HOSTS: List[str] = [h.strip() for h in allowed_hosts_str.split(",") if h.strip()]
        self.AIRGAP_LOG_BUFFER_SIZE: int = int(os.getenv("AIRGAP_LOG_BUFFER_SIZE", "500"))

        # Sandbox Execution Engine
        self.SANDBOX_DOCKER_IMAGE: str = os.getenv("SANDBOX_DOCKER_IMAGE", "python:3.11-slim")
        self.SANDBOX_TIMEOUT_SECONDS: int = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "30"))
        self.SANDBOX_MEMORY_LIMIT: str = os.getenv("SANDBOX_MEMORY_LIMIT", "512m")
        self.SANDBOX_CPU_LIMIT: float = float(os.getenv("SANDBOX_CPU_LIMIT", "1.0"))

        # Local Vector DB & Embeddings (Embedded Qdrant, zero cloud)
        self.RAG_COLLECTION_NAME: str = os.getenv("RAG_COLLECTION_NAME", "sovereign_knowledge_base")
        self.EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

        # Upload limits
        self.MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
        self.ALLOWED_EXTENSIONS: List[str] = [
            ".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".csv", ".txt", ".docx", ".pptx"
        ]

    def ensure_directories(self) -> None:
        """Ensure all required local data and storage directories exist."""
        for directory in [
            self.DATA_DIR,
            self.UPLOADS_DIR,
            self.DELIVERABLES_DIR,
            self.SAMPLES_DIR,
            self.STORAGE_DIR,
            self.QDRANT_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        """Serialize settings to a dictionary."""
        return {
            "app_name": self.APP_NAME,
            "app_version": self.APP_VERSION,
            "problem_statement_id": self.PROBLEM_STATEMENT_ID,
            "host": self.HOST,
            "port": self.PORT,
            "active_profile": self.ACTIVE_PROFILE,
            "model_base_url": self.MODEL_BASE_URL,
            "airgap_enforce": self.AIRGAP_ENFORCE,
            "airgap_allowed_hosts": self.AIRGAP_ALLOWED_HOSTS,
            "data_dir": str(self.DATA_DIR),
            "uploads_dir": str(self.UPLOADS_DIR),
            "deliverables_dir": str(self.DELIVERABLES_DIR),
            "storage_dir": str(self.STORAGE_DIR),
            "qdrant_dir": str(self.QDRANT_DIR),
        }


# Try Pydantic Settings integration if library is installed in environment
try:
    from pydantic_settings import BaseSettings as PydanticBaseSettings
    from pydantic import Field

    class PydanticSettings(PydanticBaseSettings, Settings):  # type: ignore[misc]
        model_config = {"extra": "ignore", "env_file": ".env", "env_file_encoding": "utf-8"}
except ImportError:
    pass


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve singleton application settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings


@lru_cache(maxsize=1)
def load_models_registry(config_path: Optional[Path] = None) -> dict[str, Any]:
    """Load model registry and routing configuration from YAML.

    Args:
        config_path: Optional path to models.yaml. Defaults to path from settings.

    Returns:
        Dict containing model specifications, profiles, and routing rules.
    """
    settings = get_settings()
    path = config_path or settings.MODELS_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Model configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def get_profile_config(profile_name: Optional[str] = None) -> dict[str, Any]:
    """Get active hardware profile configuration.

    Args:
        profile_name: Name of profile (e.g. 'laptop_quantized', 'server_full', 'fast_fallback').
                      Defaults to active profile in settings.

    Returns:
        Dict with profile settings including VRAM, layer offloading, and model bindings.
    """
    registry = load_models_registry()
    settings = get_settings()
    name = profile_name or settings.ACTIVE_PROFILE

    profiles = registry.get("profiles", {})
    if name not in profiles:
        raise KeyError(
            f"Hardware profile '{name}' not found. Available profiles: {list(profiles.keys())}"
        )
    return profiles[name]


def get_model_for_task(task_type: str, profile_name: Optional[str] = None) -> dict[str, Any]:
    """Determine the optimal open-weight model for a given task type.

    Args:
        task_type: Type of task (e.g. 'code_execution', 'engineering_calculation',
                   'deep_reasoning', 'vision_pid_inspection', 'scanned_document_ocr').
        profile_name: Optional profile override.

    Returns:
        Dict containing resolved model details (model_id, category, quant, context_length).
    """
    registry = load_models_registry()
    profile = get_profile_config(profile_name)
    routing_rules = registry.get("routing_rules", {})
    models_dict = registry.get("models", {})

    rule = routing_rules.get(task_type)
    if not rule:
        # Default to reasoning model if task type not explicitly routed
        primary_id = profile.get("models", {}).get("reasoning", "deepseek-r1:32b")
    else:
        primary_id = rule.get("primary", "deepseek-r1:32b")

    # If in fast_fallback profile, check if fallback model should be chosen
    profile_key = profile_name or get_settings().ACTIVE_PROFILE
    if profile_key == "fast_fallback" and rule and "fallback" in rule:
        selected_id = rule["fallback"]
    else:
        selected_id = primary_id

    model_info = models_dict.get(selected_id, {"name": selected_id, "category": "general"})

    return {
        "task_type": task_type,
        "selected_model_id": selected_id,
        "model_name": model_info.get("name", selected_id),
        "category": model_info.get("category", "general"),
        "description": model_info.get("description", ""),
        "recommended_quant": model_info.get("recommended_quant", "Q4_K_M"),
        "context_length": model_info.get("context_length", 4096),
        "profile": profile_key,
    }
