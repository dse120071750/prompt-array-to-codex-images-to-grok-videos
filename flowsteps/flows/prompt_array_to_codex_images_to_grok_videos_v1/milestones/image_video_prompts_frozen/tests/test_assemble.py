from __future__ import annotations

import importlib.util
import hashlib
import tempfile
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "assemble.py"
SPEC = importlib.util.spec_from_file_location("image_video_prompts_frozen_assemble", PATH)
assert SPEC and SPEC.loader
assemble = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assemble)


def prompt() -> str:
    return (
        "In a 3-second vertical 9:16 clip, broad paper rings expand and transform into the supplied reference image as the exact final still, then hold the completed composition. "
        "Preserve composition, subjects, object count, palette, materials, textures, and background exactly. "
        "Style: Restrained tactile 2D paper collage stop-motion, crisp machine-cut paper edges, warm cream paper keylines, halftone photographic textures, soft paper drop shadows, flat Klein Blue color field throughout. "
        "Locked camera and strict visual continuity. No 3D CGI, no photoreal environments, no text, no letters, no watermark, no UI."
    )


class AssembleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / "prompt-001.png"
        path.write_bytes(b"frozen image")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.images = [{"id": "prompt_001", "path": str(path)}]
        self.manifest_item = {"id": "prompt_001", "stable_id": "prompt-001", "index": 0, "path": "C:/attempt/prompt-001.png", "sha256": digest, "source_prompt": "source"}
        self.manifest = {"schema": "codex_image_batch_v1", "count": 1, "items": [self.manifest_item]}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_requests_private_visual_inspection(self) -> None:
        result = assemble.run({"images": self.images, "image_manifest": self.manifest})
        self.assertEqual(result["_flowstep"], "NEED_MODEL")
        self.assertEqual(result["model_request"]["required_builtin_tool"], "view_image")
        self.assertIn("Keep all visual analysis private", result["model_request"]["instruction"])

    def test_builds_ordered_motion_batch(self) -> None:
        value = prompt()
        result = assemble.run({"images": self.images, "image_manifest": self.manifest}, {"count": 1, "prompts": [value]})
        self.assertEqual(result["outputs"]["video_prompts"], [value])
        batch = result["outputs"]["manifest"]
        self.assertEqual(batch["items"][0]["source_image_sha256"], self.manifest_item["sha256"])
        self.assertEqual(batch["format"]["duration_seconds"], 3)
        self.assertEqual(batch["format"]["temporal_transform"], "reverse_and_2x")


if __name__ == "__main__":
    unittest.main()
