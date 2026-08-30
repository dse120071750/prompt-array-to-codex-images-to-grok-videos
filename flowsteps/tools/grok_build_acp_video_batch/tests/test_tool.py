from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "tool.py"
SPEC = importlib.util.spec_from_file_location("grok_build_acp_video_batch", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


FAKE_ACP = r'''
import json
import os
import sys
import time
from pathlib import Path

cwd = None
turn = 0
for raw in sys.stdin:
    request = json.loads(raw)
    method = request.get("method")
    rid = request.get("id")
    if method == "initialize":
        result = {"authMethods": [{"id": os.environ.get("FAKE_AUTH", "cached_token")}]}
    elif method == "authenticate":
        result = {
            "authenticated": True,
            "_meta": {
                "coding_data_retention_opt_out": os.environ.get("FAKE_PRIVACY") == "1",
                "is_zdr": False
            }
        }
    elif method == "session/new":
        cwd = Path(request["params"]["cwd"])
        update = {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "session-one",
                "update": {
                    "sessionUpdate": "available_commands_update",
                    "availableCommands": [],
                    "_meta": {"tools": ["image_gen", "image_to_video"] + (["read_file"] if os.environ.get("FAKE_EXTRA_TOOL") == "1" else [])}
                }
            }
        }
        print(json.dumps(update), flush=True)
        result = {"sessionId": "session-one"}
    elif method == "session/prompt":
        turn += 1
        if os.environ.get("FAKE_CRASH") == "1":
            sys.exit(7)
        if os.environ.get("FAKE_DELAY") == "1":
            time.sleep(2)
        permission_tool = os.environ.get("FAKE_PERMISSION_TOOL")
        if permission_tool:
            permission = {
                "jsonrpc": "2.0",
                "id": f"permission-{turn}",
                "method": "session/request_permission",
                "params": {
                    "sessionId": "session-one",
                    "toolCall": {
                        "toolCallId": f"tool-{turn}",
                        "title": permission_tool,
                        "_meta": {"x.ai/tool": {"name": permission_tool}}
                    },
                    "options": [
                        {"optionId": "allow-once", "name": "Allow", "kind": "allow_once"},
                        {"optionId": "reject-once", "name": "Reject", "kind": "reject_once"}
                    ]
                }
            }
            print(json.dumps(permission), flush=True)
            permission_response = json.loads(sys.stdin.readline())
            option_id = permission_response.get("result", {}).get("outcome", {}).get("optionId")
            if option_id != "allow-once":
                print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "cancelled"}}), flush=True)
                continue
        videos = cwd / "videos"
        videos.mkdir(exist_ok=True)
        count = 2 if os.environ.get("FAKE_MULTIPLE") == str(turn) else 1
        if os.environ.get("FAKE_ZERO") != str(turn):
            for suffix in range(count):
                (videos / f"turn-{turn}-{suffix}.mp4").write_bytes(f"video-{turn}-{suffix}".encode())
        update = {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "session-one",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": f"created turn {turn}"}
                }
            }
        }
        print(json.dumps(update), flush=True)
        result = {"stopReason": "end_turn"}
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}), flush=True)
'''


def batch() -> dict:
    return {
        "schema": "grok_video_prompt_batch_v1",
        "count": 2,
        "format": {"duration_seconds": 6, "aspect_ratio": "9:16", "resolution": "720p"},
        "items": [
            {"id": "prompt-001", "index": 0, "prompt": "first scene"},
            {"id": "prompt-002", "index": 1, "prompt": "second scene"},
        ],
    }


class AcpVideoBatchTests(unittest.TestCase):
    def _fake(self, root: Path) -> Path:
        path = root / "fake_acp.py"
        path.write_text(FAKE_ACP, encoding="utf-8")
        return path

    def test_one_process_and_session_generates_ordered_batch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            result = MODULE.generate_batch(
                batch(),
                root / "attempt",
                command=[sys.executable, str(fake)],
                grok_version="fake-grok 1.0",
                output_wait_seconds=2,
                media_root_resolver=lambda _session_id: root / "attempt",
            )
            self.assertEqual(result["receipt"]["session_id"], "session-one")
            self.assertTrue(result["receipt"]["started_and_completed_in_one_process"])
            self.assertEqual([item["id"] for item in result["videos"]], ["prompt-001", "prompt-002"])
            self.assertEqual(
                {clip["session_id"] for clip in result["receipt"]["clips"]},
                {"session-one"},
            )
            self.assertTrue(all(Path(item["path"]).is_file() for item in result["videos"]))
            self.assertIn("/imagine-video", result["receipt"]["clips"][0]["grok_command"])
            transcript = Path(result["receipt"]["transcript_path"]).read_text(encoding="utf-8")
            self.assertEqual(transcript.count('"method": "session/new"'), 1)
            self.assertEqual(transcript.count('"method": "session/prompt"'), 2)
            self.assertEqual(transcript.count('"method": "session/close"'), 1)

    def test_cached_login_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            environment = dict(os.environ)
            environment["FAKE_AUTH"] = "xai.api_key"
            with self.assertRaisesRegex(MODULE.AcpError, "grok login"):
                MODULE.generate_batch(
                    batch(),
                    root / "attempt",
                    command=[sys.executable, str(fake)],
                    grok_version="fake",
                    environment=environment,
                    output_wait_seconds=1,
                    media_root_resolver=lambda _session_id: root / "attempt",
                )

    def test_multiple_mp4s_fail_the_whole_batch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            environment = dict(os.environ)
            environment["FAKE_MULTIPLE"] = "2"
            attempt = root / "attempt"
            with self.assertRaisesRegex(MODULE.AcpError, "multiple MP4"):
                MODULE.generate_batch(
                    batch(),
                    attempt,
                    command=[sys.executable, str(fake)],
                    grok_version="fake",
                    environment=environment,
                    output_wait_seconds=1,
                    media_root_resolver=lambda _session_id: attempt,
                )
            failure = json.loads((attempt / "failure.json").read_text(encoding="utf-8"))
            self.assertEqual(failure["completed_ids"], ["prompt-001"])

    def test_privacy_mode_blocks_before_session_creation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            environment = dict(os.environ)
            environment["FAKE_PRIVACY"] = "1"
            environment["GROK_HOME"] = str(root / "empty-grok-home")
            attempt = root / "attempt"
            with self.assertRaisesRegex(MODULE.AcpError, "privacy/ZDR"):
                MODULE.generate_batch(
                    batch(),
                    attempt,
                    command=[sys.executable, str(fake)],
                    grok_version="fake",
                    environment=environment,
                    output_wait_seconds=1,
                    media_root_resolver=lambda _session_id: attempt,
                )
            transcript = (attempt / "acp-transcript.ndjson").read_text(encoding="utf-8")
            self.assertNotIn('"method": "session/new"', transcript)

    def test_missing_cli_has_an_actionable_error(self) -> None:
        with mock.patch.object(MODULE.shutil, "which", return_value=None):
            with self.assertRaisesRegex(FileNotFoundError, "grok login"):
                MODULE.resolve_grok_executable()

    def test_unexpected_tool_surface_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            environment = dict(os.environ)
            environment["FAKE_EXTRA_TOOL"] = "1"
            with self.assertRaisesRegex(MODULE.AcpError, "unexpected tools: read_file"):
                MODULE.generate_batch(
                    batch(),
                    root / "attempt",
                    command=[sys.executable, str(fake)],
                    grok_version="fake",
                    environment=environment,
                    output_wait_seconds=1,
                    media_root_resolver=lambda _session_id: root / "attempt",
                )

    def test_zero_mp4_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            environment = dict(os.environ)
            environment["FAKE_ZERO"] = "1"
            with self.assertRaisesRegex(MODULE.AcpError, "exactly one non-empty MP4"):
                MODULE.generate_batch(
                    batch(),
                    root / "attempt",
                    command=[sys.executable, str(fake)],
                    grok_version="fake",
                    environment=environment,
                    output_wait_seconds=0.3,
                    media_root_resolver=lambda _session_id: root / "attempt",
                )

    def test_acp_crash_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            environment = dict(os.environ)
            environment["FAKE_CRASH"] = "1"
            with self.assertRaisesRegex(MODULE.AcpError, "closed stdout|exited"):
                MODULE.generate_batch(
                    batch(),
                    root / "attempt",
                    command=[sys.executable, str(fake)],
                    grok_version="fake",
                    environment=environment,
                    output_wait_seconds=0.3,
                    media_root_resolver=lambda _session_id: root / "attempt",
                )

    def test_prompt_timeout_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            environment = dict(os.environ)
            environment["FAKE_DELAY"] = "1"
            with self.assertRaisesRegex(MODULE.AcpError, "timed out: session/prompt"):
                MODULE.generate_batch(
                    batch(),
                    root / "attempt",
                    command=[sys.executable, str(fake)],
                    grok_version="fake",
                    environment=environment,
                    prompt_timeout_seconds=0.1,
                    output_wait_seconds=0.3,
                    media_root_resolver=lambda _session_id: root / "attempt",
                )

    def test_permission_is_allowed_only_for_media_tools(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            environment = dict(os.environ)
            environment["FAKE_PERMISSION_TOOL"] = "image_gen"
            result = MODULE.generate_batch(
                batch(),
                root / "attempt",
                command=[sys.executable, str(fake)],
                grok_version="fake",
                environment=environment,
                output_wait_seconds=1,
                media_root_resolver=lambda _session_id: root / "attempt",
            )
            self.assertTrue(result["receipt"]["permission_decisions"])
            self.assertTrue(all(row["decision"] == "allow" for row in result["receipt"]["permission_decisions"]))

    def test_non_media_permission_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fake = self._fake(root)
            environment = dict(os.environ)
            environment["FAKE_PERMISSION_TOOL"] = "run_terminal_command"
            with self.assertRaisesRegex(MODULE.AcpError, "cancelled"):
                MODULE.generate_batch(
                    batch(),
                    root / "attempt",
                    command=[sys.executable, str(fake)],
                    grok_version="fake",
                    environment=environment,
                    output_wait_seconds=0.3,
                    media_root_resolver=lambda _session_id: root / "attempt",
                )


if __name__ == "__main__":
    unittest.main()
