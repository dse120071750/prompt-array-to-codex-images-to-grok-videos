from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "assemble.py"
SPEC = importlib.util.spec_from_file_location("codex_images_generated_frozen_assemble", PATH)
assert SPEC and SPEC.loader
assemble = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assemble)


BATCH = {
    "schema": "visual_prompt_batch_v1", "count": 1,
    "image": {"provider": "codex_builtin_imagegen", "aspect_ratio": "9:16"},
    "video": {"duration_seconds": 6, "aspect_ratio": "9:16", "resolution": "720p"},
    "items": [{"id": "prompt-001", "index": 0, "prompt": "detailed prompt"}],
}


class AssembleTests(unittest.TestCase):
    def test_requests_isolated_builtin_imagegen_worker(self) -> None:
        result = assemble.run({"prompt_batch": BATCH})
        self.assertEqual(result["_flowstep"], "NEED_MODEL")
        request = result["model_request"]
        self.assertEqual(request["required_builtin_tool"], "image_gen")
        self.assertIn("exactly one separate image_gen call", request["instruction"])
        self.assertIn("detailed prompt", request["instruction"])


if __name__ == "__main__":
    unittest.main()
