from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "tool.py"
SPEC = importlib.util.spec_from_file_location("prepare_visual_prompt_batch", PATH)
assert SPEC and SPEC.loader
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class ToolTests(unittest.TestCase):
    def test_preserves_order_and_freezes_settings(self) -> None:
        result = tool.run({"prompts": [" first ", "second"]})
        self.assertEqual(result["schema"], "visual_prompt_batch_v1")
        self.assertEqual([item["id"] for item in result["items"]], ["prompt-001", "prompt-002"])
        self.assertEqual([item["prompt"] for item in result["items"]], [" first ", "second"])
        self.assertEqual(result["image"], {"provider": "codex_builtin_imagegen", "aspect_ratio": "9:16"})
        self.assertEqual(result["video"], {"duration_seconds": 6, "aspect_ratio": "9:16", "resolution": "720p"})

    def test_rejects_blank_prompt(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-blank"):
            tool.run({"prompts": [" "]})

    def test_rejects_overrides(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            tool.run({"prompts": ["x"], "duration": 9})


if __name__ == "__main__":
    unittest.main()
