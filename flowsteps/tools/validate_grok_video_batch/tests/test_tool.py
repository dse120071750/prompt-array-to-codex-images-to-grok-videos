from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tool.py"
SPEC = importlib.util.spec_from_file_location("validate_grok_video_batch", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


FAKE_FFPROBE = r'''
import json
import sys
from pathlib import Path

name = Path(sys.argv[-1]).name
if "corrupt" in name:
    print("not a video", file=sys.stderr)
    raise SystemExit(1)
width, height = (1280, 720) if "landscape" in name else (720, 1280)
duration = "8.0" if "long" in name else "6.0"
print(json.dumps({
    "streams": [{"codec_type": "video", "codec_name": "h264", "width": width, "height": height, "duration": duration}],
    "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": duration}
}))
'''


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ValidateVideoBatchTests(unittest.TestCase):
    def _fixture(self, root: Path, names: list[str]) -> tuple[dict, dict, list[str]]:
        attempt = root / "attempt"
        canonical = attempt / "canonical"
        canonical.mkdir(parents=True)
        items = []
        videos = []
        clips = []
        for index, name in enumerate(names):
            item_id = f"prompt-{index + 1:03d}"
            prompt = f"scene {index}"
            path = canonical / name
            path.write_bytes(f"video-{index}".encode())
            digest = sha256(path)
            items.append({"id": item_id, "index": index, "prompt": prompt})
            videos.append({"id": item_id, "name": item_id, "path": str(path), "index": index, "prompt": prompt})
            clips.append({
                "id": item_id,
                "index": index,
                "source_prompt": prompt,
                "session_id": "one-session",
                "sha256": digest,
                "bytes": path.stat().st_size,
            })
        prompt_batch = {
            "schema": "grok_video_prompt_batch_v1",
            "count": len(items),
            "format": {"duration_seconds": 6, "aspect_ratio": "9:16", "resolution": "720p"},
            "items": items,
        }
        generation = {
            "videos": videos,
            "receipt": {
                "schema": "grok_video_batch_receipt_v1",
                "transport": "acp",
                "session_id": "one-session",
                "attempt_dir": str(attempt),
                "clips": clips,
            },
        }
        fake = root / "fake_ffprobe.py"
        fake.write_text(FAKE_FFPROBE, encoding="utf-8")
        return prompt_batch, generation, [sys.executable, str(fake)]

    def test_valid_portrait_batch_passes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            prompt_batch, generation, command = self._fixture(Path(raw), ["prompt-001.mp4", "prompt-002.mp4"])
            result = MODULE.validate_batch(prompt_batch, generation, ffprobe_command=command)
            self.assertTrue(result["validation"]["ok"])
            self.assertEqual(result["validation"]["count"], 2)
            self.assertEqual(result["videos"][0]["width"], 720)
            self.assertEqual(result["videos"][0]["height"], 1280)

    def test_landscape_video_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            prompt_batch, generation, command = self._fixture(Path(raw), ["landscape.mp4"])
            with self.assertRaisesRegex(ValueError, "720x1280"):
                MODULE.validate_batch(prompt_batch, generation, ffprobe_command=command)

    def test_path_outside_attempt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prompt_batch, generation, command = self._fixture(root, ["prompt-001.mp4"])
            outside = root / "outside.mp4"
            outside.write_bytes(b"outside")
            generation["videos"][0]["path"] = str(outside)
            with self.assertRaisesRegex(ValueError, "escaped"):
                MODULE.validate_batch(prompt_batch, generation, ffprobe_command=command)

    def test_invalid_duration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            prompt_batch, generation, command = self._fixture(Path(raw), ["long.mp4"])
            with self.assertRaisesRegex(ValueError, "approximately 6 seconds"):
                MODULE.validate_batch(prompt_batch, generation, ffprobe_command=command)

    def test_corrupt_mp4_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            prompt_batch, generation, command = self._fixture(Path(raw), ["corrupt.mp4"])
            with self.assertRaisesRegex(ValueError, "ffprobe rejected"):
                MODULE.validate_batch(prompt_batch, generation, ffprobe_command=command)


if __name__ == "__main__":
    unittest.main()
