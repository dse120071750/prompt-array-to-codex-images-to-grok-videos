from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image


PATH = Path(__file__).resolve().parents[1] / "tool.py"
SPEC = importlib.util.spec_from_file_location("freeze_codex_image_batch", PATH)
assert SPEC and SPEC.loader
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def batch(prompts: list[str]) -> dict:
    return {
        "schema": "visual_prompt_batch_v1",
        "count": len(prompts),
        "image": {"provider": "codex_builtin_imagegen", "aspect_ratio": "9:16"},
        "video": {"duration_seconds": 6, "aspect_ratio": "9:16", "resolution": "720p"},
        "items": [{"id": f"prompt-{i + 1:03d}", "index": i, "prompt": prompt} for i, prompt in enumerate(prompts)],
    }


def make_image(path: Path, size: tuple[int, int] = (90, 160), color: str = "blue") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


class ToolTests(unittest.TestCase):
    def test_imports_ordered_batch_with_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "generated_images"
            work = Path(temp) / "run" / "work"
            a, b = root / "thread" / "a.png", root / "thread" / "b.png"
            make_image(a, color="blue")
            make_image(b, color="red")
            prompts = ["first", "second"]
            draft = {"count": 2, "images": [
                {"id": "prompt-001", "index": 0, "source_prompt": "first", "image_prompt": "first", "generated_file": str(a)},
                {"id": "prompt-002", "index": 1, "source_prompt": "second", "image_prompt": "second", "generated_file": str(b)},
            ]}
            result = tool.run({"prompt_batch": batch(prompts), "draft": draft, "work_dir": str(work), "_test_allowed_generated_root": str(root), "not_before_epoch": time.time() - 5})
            self.assertEqual(result["manifest"]["count"], 2)
            self.assertEqual([item["id"] for item in result["images"]], ["prompt_001", "prompt_002"])
            self.assertEqual([item["stable_id"] for item in result["images"]], ["prompt-001", "prompt-002"])
            self.assertTrue(all(Path(item["path"]).is_file() for item in result["images"]))
            self.assertTrue(all(len(item["sha256"]) == 64 for item in result["images"]))
            self.assertEqual(result["images"], result["manifest"]["items"])

    def test_rejects_path_outside_codex_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root, outside = base / "generated_images", base / "outside.png"
            root.mkdir()
            make_image(outside)
            draft = {"count": 1, "images": [{"id": "prompt-001", "index": 0, "source_prompt": "x", "image_prompt": "x", "generated_file": str(outside)}]}
            with self.assertRaisesRegex(ValueError, "escaped"):
                tool.run({"prompt_batch": batch(["x"]), "draft": draft, "work_dir": str(base / "work"), "_test_allowed_generated_root": str(root)})

    def test_rejects_duplicate_source_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "generated_images"
            image = root / "one.png"
            make_image(image)
            draft = {"count": 2, "images": [
                {"id": "prompt-001", "index": 0, "source_prompt": "a", "image_prompt": "a", "generated_file": str(image)},
                {"id": "prompt-002", "index": 1, "source_prompt": "b", "image_prompt": "b", "generated_file": str(image)},
            ]}
            with self.assertRaisesRegex(ValueError, "distinct"):
                tool.run({"prompt_batch": batch(["a", "b"]), "draft": draft, "work_dir": str(Path(temp) / "work"), "_test_allowed_generated_root": str(root)})

    def test_rejects_stale_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "generated_images"
            image = root / "old.png"
            make_image(image)
            old = time.time() - 100
            os.utime(image, (old, old))
            draft = {"count": 1, "images": [{"id": "prompt-001", "index": 0, "source_prompt": "x", "image_prompt": "x", "generated_file": str(image)}]}
            with self.assertRaisesRegex(ValueError, "predates"):
                tool.run({"prompt_batch": batch(["x"]), "draft": draft, "work_dir": str(Path(temp) / "work"), "_test_allowed_generated_root": str(root), "not_before_epoch": time.time()})

    def test_rejects_wrong_aspect_and_prompt_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "generated_images"
            image = root / "square.png"
            make_image(image, size=(100, 100))
            drift = {"count": 1, "images": [{"id": "prompt-001", "index": 0, "source_prompt": "x", "image_prompt": "changed", "generated_file": str(image)}]}
            with self.assertRaisesRegex(ValueError, "verbatim"):
                tool.run({"prompt_batch": batch(["x"]), "draft": drift, "work_dir": str(Path(temp) / "work"), "_test_allowed_generated_root": str(root)})
            drift["images"][0]["image_prompt"] = "x"
            with self.assertRaisesRegex(ValueError, "portrait"):
                tool.run({"prompt_batch": batch(["x"]), "draft": drift, "work_dir": str(Path(temp) / "work"), "_test_allowed_generated_root": str(root)})


if __name__ == "__main__":
    unittest.main()
