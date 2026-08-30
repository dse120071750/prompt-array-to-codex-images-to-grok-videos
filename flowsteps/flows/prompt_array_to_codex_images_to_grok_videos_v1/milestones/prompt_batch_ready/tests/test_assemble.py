from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "assemble.py"
SPEC = importlib.util.spec_from_file_location("prompt_batch_ready_assemble", PATH)
assert SPEC and SPEC.loader
assemble = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assemble)


class AssembleTests(unittest.TestCase):
    def test_freezes_request(self) -> None:
        result = assemble.run({"request": {"prompts": ["a", "b"]}})
        self.assertEqual(result["outputs"]["batch"]["count"], 2)


if __name__ == "__main__":
    unittest.main()
