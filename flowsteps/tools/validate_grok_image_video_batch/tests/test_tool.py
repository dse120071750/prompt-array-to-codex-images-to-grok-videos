from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "tool.py"
SPEC = importlib.util.spec_from_file_location("validate_grok_image_video_batch", PATH)
assert SPEC and SPEC.loader
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class FakeValidator:
    @staticmethod
    def probe_video(path, command):
        del path, command
        return {}

    @staticmethod
    def _video_metadata(path, probe, *, allowed_dimensions=None, duration_range=(5.5, 6.5)):
        del probe
        if (720, 1264) not in (allowed_dimensions or set()):
            raise ValueError("native Grok dimensions were not allowed")
        if duration_range != (2.8, 3.2):
            raise ValueError("three-second final duration was not required")
        data = path.read_bytes()
        return {"width": 720, "height": 1264, "duration_seconds": 3.0, "format_name": "mov,mp4", "video_codec": "h264", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate(root: Path):
    video = root / "attempt" / "canonical" / "prompt-001.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    digest = hashlib.sha256(b"video").hexdigest()
    image_sha = "a" * 64
    images = [{"id": "prompt-001", "index": 0, "sha256": image_sha}]
    prompts = {"items": [{"id": "prompt-001", "index": 0, "source_image_sha256": image_sha, "video_prompt": "move"}]}
    clip = {"id": "prompt-001", "index": 0, "source_image_sha256": image_sha, "video_prompt": "move", "session_id": "s", "sha256": digest, "bytes": 5}
    generation = {
        "videos": [{"id": "prompt-001", "index": 0, "path": str(video), "source_image_sha256": image_sha, "video_prompt": "move"}],
        "receipt": {"schema": "grok_image_video_batch_receipt_v1", "transport": "acp", "session_id": "s", "allowed_tools": ["image_to_video"], "attempt_dir": str(root / "attempt"), "count": 1, "clips": [clip]},
    }
    return images, prompts, generation


class ToolTests(unittest.TestCase):
    def test_accepts_complete_technical_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.object(tool, "_video_validator", return_value=FakeValidator):
            result = tool.validate_batch(*candidate(Path(temp)), ffprobe_command=["fake-ffprobe"])
            self.assertTrue(result["validation"]["ok"])
            self.assertEqual(result["videos"][0]["width"], 720)
            self.assertEqual(result["videos"][0]["height"], 1264)

    def test_rejects_prompt_or_image_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.object(tool, "_video_validator", return_value=FakeValidator):
            images, prompts, generation = candidate(Path(temp))
            generation["videos"][0]["video_prompt"] = "changed"
            with self.assertRaisesRegex(ValueError, "motion prompt changed"):
                tool.validate_batch(images, prompts, generation, ffprobe_command=["fake"])

    def test_rejects_video_outside_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.object(tool, "_video_validator", return_value=FakeValidator):
            root = Path(temp)
            images, prompts, generation = candidate(root)
            outside = root / "outside.mp4"; outside.write_bytes(b"video")
            generation["videos"][0]["path"] = str(outside)
            with self.assertRaisesRegex(ValueError, "escaped"):
                tool.validate_batch(images, prompts, generation, ffprobe_command=["fake"])


if __name__ == "__main__":
    unittest.main()
