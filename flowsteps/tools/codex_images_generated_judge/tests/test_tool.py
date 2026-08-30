from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "tool.py"
SPEC = importlib.util.spec_from_file_location("codex_images_generated_judge", PATH)
assert SPEC and SPEC.loader
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class ToolTests(unittest.TestCase):
    def test_accepts_complete_mapping_and_rejects_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "prompt-001.png"
            path.write_bytes(b"image")
            item = {"id": "prompt_001", "stable_id": "prompt-001", "name": "still", "path": str(path), "index": 0, "source_prompt": "x", "image_prompt": "x", "sha256": "a" * 64, "bytes": 5, "width": 90, "height": 160, "mime_type": "image/png", "image_format": "PNG"}
            batch = {"items": [{"id": "prompt-001", "index": 0, "prompt": "x"}]}
            frozen = {"images": [item], "manifest": {"schema": "codex_image_batch_v1", "provider": "codex_builtin_imagegen", "count": 1, "items": [dict(item)]}}
            self.assertTrue(tool.run({"prompt_batch": batch, "frozen": frozen})["ok"])
            frozen["manifest"]["items"][0]["source_prompt"] = "changed"
            rejected = tool.run({"prompt_batch": batch, "frozen": frozen})
            self.assertFalse(rejected["ok"])
            self.assertIn("differ", " ".join(rejected["findings"]))


if __name__ == "__main__":
    unittest.main()
