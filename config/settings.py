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


def _parse_int_env(name: str, default: str, *, min_val: int | None = None) -> int:
    """Parse an integer environment variable with optional minimum validation."""
    raw = os.getenv(name, default)
    try:
        val = int(raw)
    except ValueError:
        raise ValueError(f"Environment variable {name}={raw!r} is not a valid integer")
    if min_val is not None and val < min_val:
        raise ValueError(f"Environment variable {name}={val} must be >= {min_val}")
    return val


def _parse_float_env(name: str, default: str, *, min_val: float | None = None) -> float:
    """Parse a float environment variable with optional minimum validation."""
    raw = os.getenv(name, default)
    try:
        val = float(raw)
    except ValueError:
        raise ValueError(f"Environment variable {name}={raw!r} is not a valid number")
    if min_val is not None and val < min_val:
        raise ValueError(f"Environment variable {name}={val} must be >= {min_val}")
    return val


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
        self.PORT: int = _parse_int_env("PORT", "8000", min_val=1)
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

        # Model Server (OpenAI-compatible local server, e.g. Ollama or llama-server)
        self.MODEL_BASE_URL: str = os.getenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1")
        self.MODEL_TIMEOUT_SECONDS: float = _parse_float_env("MODEL_TIMEOUT_SECONDS", "120.0", min_val=1.0)
        self.ACTIVE_PROFILE: str = os.getenv("ACTIVE_PROFILE", "laptop_quantized")

        # Air-Gap Enforcement & Network Monitor
        self.AIRGAP_ENFORCE: bool = os.getenv("AIRGAP_ENFORCE", "true").lower() in ("true", "1", "yes")
        allowed_hosts_str = os.getenv("AIRGAP_ALLOWED_HOSTS", "127.0.0.1,localhost,::1")
        self.AIRGAP_ALLOWED_HOSTS: List[str] = [h.strip() for h in allowed_hosts_str.split(",") if h.strip()]
        self.AIRGAP_LOG_BUFFER_SIZE: int = _parse_int_env("AIRGAP_LOG_BUFFER_SIZE", "500", min_val=1)

        # Sandbox Execution Engine
        self.SANDBOX_DOCKER_IMAGE: str = os.getenv("SANDBOX_DOCKER_IMAGE", "python:3.11-slim")
        self.SANDBOX_TIMEOUT_SECONDS: int = _parse_int_env("SANDBOX_TIMEOUT_SECONDS", "30", min_val=1)
        self.SANDBOX_MEMORY_LIMIT: str = os.getenv("SANDBOX_MEMORY_LIMIT", "512m")
        self.SANDBOX_CPU_LIMIT: float = _parse_float_env("SANDBOX_CPU_LIMIT", "1.0", min_val=0.1)
        self.SCRATCH_DIR: Path = Path(os.getenv("SCRATCH_DIR", str(self.BASE_DIR / "scratch")))

        # Local Vector DB & Embeddings (Embedded Qdrant, zero cloud)
        self.RAG_COLLECTION_NAME: str = os.getenv("RAG_COLLECTION_NAME", "sovereign_knowledge_base")
        self.EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

        # Upload limits
        self.MAX_UPLOAD_SIZE_MB: int = _parse_int_env("MAX_UPLOAD_SIZE_MB", "50", min_val=1)
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
            self.SCRATCH_DIR,
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
            "debug": self.DEBUG,
            "active_profile": self.ACTIVE_PROFILE,
            "model_base_url": self.MODEL_BASE_URL,
            "model_timeout_seconds": self.MODEL_TIMEOUT_SECONDS,
            "airgap_enforce": self.AIRGAP_ENFORCE,
            "airgap_allowed_hosts": self.AIRGAP_ALLOWED_HOSTS,
            "airgap_log_buffer_size": self.AIRGAP_LOG_BUFFER_SIZE,
            "data_dir": str(self.DATA_DIR),
            "uploads_dir": str(self.UPLOADS_DIR),
            "deliverables_dir": str(self.DELIVERABLES_DIR),
            "samples_dir": str(self.SAMPLES_DIR),
            "storage_dir": str(self.STORAGE_DIR),
            "qdrant_dir": str(self.QDRANT_DIR),
            "scratch_dir": str(self.SCRATCH_DIR),
            "sandbox_docker_image": self.SANDBOX_DOCKER_IMAGE,
            "sandbox_timeout_seconds": self.SANDBOX_TIMEOUT_SECONDS,
            "sandbox_memory_limit": self.SANDBOX_MEMORY_LIMIT,
            "sandbox_cpu_limit": self.SANDBOX_CPU_LIMIT,
            "rag_collection_name": self.RAG_COLLECTION_NAME,
            "embedding_model": self.EMBEDDING_MODEL,
            "max_upload_size_mb": self.MAX_UPLOAD_SIZE_MB,
            "allowed_extensions": self.ALLOWED_EXTENSIONS,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve singleton application settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings


@lru_cache(maxsize=1)
def load_models_registry() -> dict[str, Any]:
    """Load model registry and routing configuration from YAML.

    Always reads from the path specified in settings (MODELS_CONFIG_PATH).
    Cached after first successful load; call .cache_clear() to reload.

    Returns:
        Dict containing model specifications, profiles, and routing rules.
    """
    settings = get_settings()
    path = settings.MODELS_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Model configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Model configuration file is empty or invalid: {path}")

    # Basic structure validation
    for required_key in ("models", "profiles"):
        if required_key not in data:
            raise ValueError(
                f"Model configuration missing required key '{required_key}' in {path}"
            )

    return data


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
