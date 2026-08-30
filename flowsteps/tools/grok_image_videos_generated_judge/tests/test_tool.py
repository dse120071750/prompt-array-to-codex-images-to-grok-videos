from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "tool.py"
SPEC = importlib.util.spec_from_file_location("grok_image_videos_generated_judge", PATH)
assert SPEC and SPEC.loader
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def payload():
    return {
        "images": [{"id": "prompt-001"}],
        "video_prompts": {"items": [{"id": "prompt-001"}]},
        "validated": {
            "videos": [{"id": "prompt-001"}],
            "validation": {"ok": True},
            "receipt": {"count": 1, "session_id": "s", "allowed_tools": ["image_to_video"], "clips": [{"session_id": "s"}]},
        },
    }


class ToolTests(unittest.TestCase):
    def test_accepts_one_complete_session(self) -> None:
        self.assertTrue(tool.run(payload())["ok"])

    def test_rejects_multi_session(self) -> None:
        value = payload()
        value["validated"]["receipt"]["clips"][0]["session_id"] = "other"
        with self.assertRaisesRegex(ValueError, "more than one ACP session"):
            tool.run(value)


if __name__ == "__main__":
    unittest.main()
