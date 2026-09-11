"""Unit and smoke tests for configuration and model registry."""

import os
import unittest
from pathlib import Path
from config.settings import (
    Settings,
    get_settings,
    load_models_registry,
    get_profile_config,
    get_model_for_task,
)


class TestConfigAndRegistry(unittest.TestCase):
    """Test suite for settings and model registry."""

    def setUp(self) -> None:
        get_settings.cache_clear()
        load_models_registry.cache_clear()

    def test_settings_initialization(self) -> None:
        """Verify default settings values and directory paths."""
        settings = Settings()
        self.assertEqual(settings.PROBLEM_STATEMENT_ID, "26117")
        self.assertEqual(settings.HOST, "127.0.0.1")
        self.assertEqual(settings.PORT, 8000)
        self.assertTrue(settings.AIRGAP_ENFORCE)
        self.assertIn("127.0.0.1", settings.AIRGAP_ALLOWED_HOSTS)
        self.assertEqual(settings.ACTIVE_PROFILE, "laptop_quantized")

        # Directories should be subpaths of BASE_DIR
        self.assertTrue(settings.DATA_DIR.is_relative_to(settings.BASE_DIR))
        self.assertTrue(settings.UPLOADS_DIR.is_relative_to(settings.DATA_DIR))
        self.assertTrue(settings.DELIVERABLES_DIR.is_relative_to(settings.DATA_DIR))
        self.assertTrue(settings.STORAGE_DIR.is_relative_to(settings.BASE_DIR))
        self.assertTrue(settings.QDRANT_DIR.is_relative_to(settings.STORAGE_DIR))

    def test_ensure_directories(self) -> None:
        """Verify that ensure_directories creates the required folder structure."""
        settings = get_settings()
        settings.ensure_directories()
        self.assertTrue(settings.UPLOADS_DIR.exists())
        self.assertTrue(settings.DELIVERABLES_DIR.exists())
        self.assertTrue(settings.SAMPLES_DIR.exists())
        self.assertTrue(settings.QDRANT_DIR.exists())

    def test_models_registry_content(self) -> None:
        """Verify models.yaml contains requested models and valid structure."""
        registry = load_models_registry()
        self.assertIn("models", registry)
        self.assertIn("profiles", registry)
        self.assertIn("routing_rules", registry)

        models = registry["models"]
        # Required models from problem statement & implementation plan
        self.assertIn("deepseek-r1:32b", models)
        self.assertIn("qwen3.8-27b", models)
        self.assertIn("qwen2-vl:7b", models)
        self.assertIn("docling", models)

    def test_hardware_profiles(self) -> None:
        """Verify laptop_quantized and server_full hardware profiles."""
        laptop = get_profile_config("laptop_quantized")
        self.assertEqual(laptop["vram_gb"], 6)
        self.assertEqual(laptop["ram_gb"], 16)
        self.assertIn("deepseek-r1:32b", laptop["gpu_layers_offload"])
        self.assertIn("qwen3.8-27b", laptop["gpu_layers_offload"])

        server = get_profile_config("server_full")
        self.assertEqual(server["vram_gb"], 48)

        fallback = get_profile_config("fast_fallback")
        self.assertEqual(fallback["models"]["reasoning"], "deepseek-r1:7b")

    def test_task_to_model_routing(self) -> None:
        """Verify dynamic auto-routing for different task types."""
        # Code and math routes to qwen3.8-27b
        code_model = get_model_for_task("code_execution")
        self.assertEqual(code_model["selected_model_id"], "qwen3.8-27b")

        math_model = get_model_for_task("engineering_calculation")
        self.assertEqual(math_model["selected_model_id"], "qwen3.8-27b")

        # Reasoning and SOP compliance routes to deepseek-r1:32b
        reasoning_model = get_model_for_task("deep_reasoning")
        self.assertEqual(reasoning_model["selected_model_id"], "deepseek-r1:32b")

        sop_model = get_model_for_task("sop_compliance")
        self.assertEqual(sop_model["selected_model_id"], "deepseek-r1:32b")

        # Multimodal P&ID inspection routes to qwen2-vl:7b
        vision_model = get_model_for_task("vision_pid_inspection")
        self.assertEqual(vision_model["selected_model_id"], "qwen2-vl:7b")

        # Fast fallback profile routing
        fallback_code = get_model_for_task("code_execution", profile_name="fast_fallback")
        self.assertEqual(fallback_code["selected_model_id"], "qwen2.5-coder:7b")

        fallback_reasoning = get_model_for_task("deep_reasoning", profile_name="fast_fallback")
        self.assertEqual(fallback_reasoning["selected_model_id"], "deepseek-r1:7b")


if __name__ == "__main__":
    unittest.main()
