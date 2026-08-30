from __future__ import annotations

import importlib.util
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "assemble.py"
SPEC = importlib.util.spec_from_file_location("grok_videos_generated_frozen_assemble", PATH)
assert SPEC and SPEC.loader
assemble = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assemble)


class AssembleTests(unittest.TestCase):
    def test_rejects_missing_chosen_inputs_before_live_generation(self) -> None:
        with self.assertRaises(ValueError):
            assemble.run({})

    def test_accepts_public_prompt_array_bound_to_internal_manifest(self) -> None:
        prompt_batch = {"schema": "visual_prompt_batch_v1", "items": [], "count": 1}
        prompt_array = ["motion"]
        prompt_manifest = {"schema": "image_video_prompt_batch_v1", "prompts": prompt_array, "items": [{"id": "prompt-001"}], "count": 1}

        class Generator:
            @staticmethod
            def run(value):
                self.assertIs(value["video_prompts"], prompt_manifest)
                return {"generated": True}

        class Validator:
            @staticmethod
            def run(value):
                self.assertEqual(value["video_prompts"], prompt_manifest)
                return {"videos": [{"id": "prompt-001"}], "receipt": {"count": 1}, "validation": {"ok": True}}

        class Judge:
            @staticmethod
            def run(value):
                self.assertEqual(value["video_prompts"], prompt_manifest)
                return {"ok": True, "code": "pass"}

        tools = {"grok_build_acp_image_video_batch": Generator, "validate_grok_image_video_batch": Validator, "grok_image_videos_generated_judge": Judge}
        with tempfile.TemporaryDirectory() as temp, patch.object(assemble, "_load_tool", side_effect=lambda name: tools[name]):
            image_path = Path(temp) / "frozen.png"
            image_path.write_bytes(b"frozen image")
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            images = [{"id": "prompt_001", "path": str(image_path)}]
            image_manifest = {"schema": "codex_image_batch_v1", "items": [{"id": "prompt_001", "stable_id": "prompt-001", "index": 0, "path": "C:/attempt/frozen.png", "sha256": digest}], "count": 1}
            result = assemble.run({"prompt_batch": prompt_batch, "images": images, "image_manifest": image_manifest, "video_prompts": prompt_array, "video_prompt_manifest": prompt_manifest}, run_dir=temp)
        self.assertEqual(result["outputs"]["videos"], [{"id": "video_001", "stable_id": "prompt-001", "name": "Grok image-derived video 001"}])


if __name__ == "__main__":
    unittest.main()
