from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "tool.py"
SPEC = importlib.util.spec_from_file_location("image_video_prompts_judge", PATH)
assert SPEC and SPEC.loader
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def valid_prompt(unique: str = "") -> str:
    core = (
        "In a 3-second vertical 9:16 clip, broad paper rings expand across the canvas and transform into the supplied reference image as the exact final still, then hold the completed composition decisively. "
        "Preserve the final composition, subjects, object count, palette, materials, textures, and background exactly. "
        "Style: Restrained tactile 2D paper collage stop-motion, crisp machine-cut paper edges, warm cream paper keylines, halftone photographic textures, soft paper drop shadows, flat Klein Blue color field throughout. "
        "Locked camera and strict visual continuity. No 3D CGI, no photoreal environments, no text, no letters, no watermark, no UI. "
    )
    return core + unique + " Hold all final details and spatial relationships without drift."


class ToolTests(unittest.TestCase):
    def test_accepts_complete_ordered_array(self) -> None:
        result = tool.run({"images": [{"id": "prompt-001"}, {"id": "prompt-002"}], "draft": {"count": 2, "prompts": [valid_prompt(" one"), valid_prompt(" two")]}})
        self.assertTrue(result["ok"], result["findings"])

    def test_rejects_wrong_count_and_final_target(self) -> None:
        result = tool.run({"images": [{"id": "prompt-001"}, {"id": "prompt-002"}], "draft": {"count": 1, "prompts": ["Wrong opener"]}})
        self.assertFalse(result["ok"])
        self.assertIn("exactly equal", " ".join(result["findings"]))

    def test_rejects_cross_image_reference_and_analysis(self) -> None:
        result = tool.run({"images": [{"id": "prompt-001"}], "draft": {"count": 1, "prompts": [valid_prompt(" Compare with image 2. Visual analysis: hidden notes.")]}})
        self.assertFalse(result["ok"])
        text = " ".join(result["findings"])
        self.assertIn("only its own", text)
        self.assertIn("exposes visual analysis", text)

    def test_hand_must_enter_from_outside_canvas(self) -> None:
        result = tool.run({"images": [{"id": "prompt-001", "source_prompt": "a hand placing a bridge"}], "draft": {"count": 1, "prompts": [valid_prompt()]}})
        self.assertFalse(result["ok"])
        self.assertIn("outside the canvas", " ".join(result["findings"]))


if __name__ == "__main__":
    unittest.main()
