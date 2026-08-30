from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PATH = Path(__file__).resolve().parents[1] / "tool.py"
SPEC = importlib.util.spec_from_file_location("grok_build_acp_image_video_batch", PATH)
assert SPEC and SPEC.loader
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class FakeProcess:
    def __init__(self) -> None:
        self.returncode = None

    def poll(self):
        return self.returncode


class FakeClient:
    def __init__(self, media_root: Path, *, tools=None, privacy=False, output_mode="one") -> None:
        self.media_root = media_root
        self.tools = tools or ["image_to_video"]
        self.privacy = privacy
        self.output_mode = output_mode
        self.calls: list[tuple[str, dict]] = []
        self.prompt_texts: list[str] = []
        self.process = FakeProcess()
        self.permission_decisions = []
        self.prompt_count = 0

    def request(self, method, params, *, timeout_seconds, on_update=None):
        del timeout_seconds
        self.calls.append((method, params))
        if method == "initialize":
            return {"authMethods": [{"id": "cached_token"}]}
        if method == "authenticate":
            return {"_meta": {"coding_data_retention_opt_out": self.privacy, "is_zdr": False}}
        if method == "session/new":
            self.media_root.mkdir(parents=True, exist_ok=True)
            if on_update:
                on_update({"method": "session/update", "params": {"sessionId": "session-one", "update": {"sessionUpdate": "available_commands_update", "_meta": {"tools": self.tools}}}})
            return {"sessionId": "session-one"}
        if method == "session/prompt":
            self.prompt_count += 1
            text = params["prompt"][0]["text"]
            self.prompt_texts.append(text)
            videos = self.media_root / "videos"
            videos.mkdir(exist_ok=True)
            if self.output_mode == "one":
                (videos / f"clip-{self.prompt_count}.mp4").write_bytes(f"video-{self.prompt_count}".encode())
            elif self.output_mode == "multiple":
                (videos / f"clip-{self.prompt_count}-a.mp4").write_bytes(b"a")
                (videos / f"clip-{self.prompt_count}-b.mp4").write_bytes(b"b")
            if on_update:
                on_update({"method": "session/update", "params": {"sessionId": "session-one", "update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "done"}}}})
            return {"stopReason": "end_turn"}
        if method == "session/close":
            self.process.returncode = 0
            return {}
        raise AssertionError(method)

    def drain_updates(self, **kwargs):
        del kwargs

    def close(self):
        self.process.returncode = 0


def make_inputs(run_dir: Path, count: int = 2):
    prompts = [f"source {i}" for i in range(count)]
    prompt_batch = {
        "schema": "visual_prompt_batch_v1", "count": count,
        "image": {"provider": "codex_builtin_imagegen", "aspect_ratio": "9:16"},
        "video": {"duration_seconds": 6, "aspect_ratio": "9:16", "resolution": "720p"},
        "items": [{"id": f"prompt-{i + 1:03d}", "index": i, "prompt": prompts[i]} for i in range(count)],
    }
    images = []
    for i in range(count):
        path = run_dir / "images" / f"prompt-{i + 1:03d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (90, 160), "blue").save(path)
        images.append({"id": f"prompt-{i + 1:03d}", "index": i, "path": str(path), "source_prompt": prompts[i], "sha256": tool._sha256(path)})
    manifest_items = []
    for i, image in enumerate(images):
        item = dict(image)
        item["id"] = f"prompt_{i + 1:03d}"
        item["stable_id"] = f"prompt-{i + 1:03d}"
        manifest_items.append(item)
    manifest = {"schema": "codex_image_batch_v1", "count": count, "items": manifest_items}
    video_prompts = {
        "schema": "image_video_prompt_batch_v1", "count": count,
        "format": {"duration_seconds": 3, "aspect_ratio": "9:16", "resolution": "720p", "grok_master_duration_seconds": 6, "temporal_transform": "reverse_and_2x"},
        "items": [{"id": f"prompt-{i + 1:03d}", "index": i, "source_prompt": prompts[i], "source_image_path": images[i]["path"], "source_image_sha256": images[i]["sha256"], "video_prompt": f"motion prompt {i}"} for i in range(count)],
    }
    return prompt_batch, images, manifest, video_prompts


class ToolTests(unittest.TestCase):
    def test_one_process_one_session_and_ordered_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir, attempt, transport, media = root / "run", root / "attempt", root / "transport", root / "media"
            run_dir.mkdir(); transport.mkdir()
            inputs = make_inputs(run_dir)
            clients = []
            def factory(*args, **kwargs):
                del args, kwargs
                client = FakeClient(media)
                clients.append(client)
                return client
            result = tool.generate_batch(*inputs, attempt, run_dir=run_dir, command=["fake"], grok_version="fake 1", transport_cwd=transport, media_root_resolver=lambda _: media, client_factory=factory, video_postprocessor=lambda master, final: shutil.copy2(master, final), output_wait_seconds=2)
            self.assertEqual(len(clients), 1)
            methods = [method for method, _ in clients[0].calls]
            self.assertEqual(methods.count("session/new"), 1)
            self.assertEqual(methods.count("session/prompt"), 2)
            self.assertEqual(result["receipt"]["session_id"], "session-one")
            self.assertEqual(result["receipt"]["allowed_tools"], ["image_to_video"])
            self.assertIn('image: "images/prompt-001.png"', clients[0].prompt_texts[0])
            self.assertIn("motion prompt 1", clients[0].prompt_texts[1])
            self.assertIn("6-second reverse-motion master", clients[0].prompt_texts[0])
            self.assertEqual(result["receipt"]["format"]["duration_seconds"], 3)
            self.assertEqual([item["id"] for item in result["videos"]], ["prompt-001", "prompt-002"])

    def test_privacy_blocks_before_session_new(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir, transport, media = root / "run", root / "transport", root / "media"
            run_dir.mkdir(); transport.mkdir()
            inputs = make_inputs(run_dir, 1)
            client = FakeClient(media, privacy=True)
            with self.assertRaisesRegex(RuntimeError, "privacy/ZDR"):
                tool.generate_batch(*inputs, root / "attempt", run_dir=run_dir, command=["fake"], grok_version="fake", environment={"USERPROFILE": str(root / "home")}, transport_cwd=transport, media_root_resolver=lambda _: media, client_factory=lambda *a, **k: client)
            self.assertNotIn("session/new", [method for method, _ in client.calls])

    def test_rejects_unexpected_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir, transport, media = root / "run", root / "transport", root / "media"
            run_dir.mkdir(); transport.mkdir()
            inputs = make_inputs(run_dir, 1)
            client = FakeClient(media, tools=["image_to_video", "image_gen"])
            with self.assertRaisesRegex(RuntimeError, "allowlist"):
                tool.generate_batch(*inputs, root / "attempt", run_dir=run_dir, command=["fake"], grok_version="fake", transport_cwd=transport, media_root_resolver=lambda _: media, client_factory=lambda *a, **k: client)

    def test_multiple_mp4s_in_one_turn_invalidates_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir, transport, media = root / "run", root / "transport", root / "media"
            run_dir.mkdir(); transport.mkdir()
            inputs = make_inputs(run_dir, 1)
            client = FakeClient(media, output_mode="multiple")
            with self.assertRaisesRegex(RuntimeError, "multiple MP4"):
                tool.generate_batch(*inputs, root / "attempt", run_dir=run_dir, command=["fake"], grok_version="fake", transport_cwd=transport, media_root_resolver=lambda _: media, client_factory=lambda *a, **k: client, output_wait_seconds=1)
            self.assertTrue((root / "attempt" / "failure.json").is_file())

    def test_rejects_source_image_outside_current_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run"; run_dir.mkdir()
            inputs = list(make_inputs(run_dir, 1))
            outside = root / "outside.png"
            Image.new("RGB", (90, 160), "blue").save(outside)
            inputs[1][0]["path"] = str(outside)
            inputs[1][0]["sha256"] = tool._sha256(outside)
            inputs[2]["items"][0]["sha256"] = tool._sha256(outside)
            inputs[3]["items"][0]["source_image_path"] = str(outside)
            inputs[3]["items"][0]["source_image_sha256"] = tool._sha256(outside)
            with self.assertRaisesRegex(ValueError, "escaped"):
                tool._validate_inputs(*inputs, run_dir)


if __name__ == "__main__":
    unittest.main()
