"""Generate an ordered video batch through one persistent Grok Build ACP session.

This module intentionally contains no HTTP client and no xAI video API URL.
All media generation is delegated to the locally installed ``grok agent stdio``
process and its canonical ``/imagine-video`` command.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # Python 3.10 in the bundled M8M runtime.
    import tomli as tomllib  # type: ignore[no-redef]


PROMPT_TEMPLATE = """/imagine-video Create exactly one 6-second, vertical 9:16, 720p video.
Preserve all subjects, objects, composition, colors, and art direction from
the source prompt. Use subtle physical movement and one simple camera move.
Do not create multiple shots, concatenate clips, add captions, or add text.
Use only the image_gen and image_to_video tools. If either media tool fails,
report the exact failure and stop. Do not use terminal, filesystem, search,
workflow, subagent, scheduler, or any other tool.
When calling image_to_video, use the generated image's short session-relative
path exactly (for example images/1.jpg), never its absolute path.

SOURCE PROMPT:
{prompt}"""

ALLOWED_MEDIA_TOOLS = frozenset({"image_gen", "image_to_video"})


class AcpError(RuntimeError):
    """Raised when the Grok Build ACP transport or protocol fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, path: Path) -> bool:
    root = root.resolve()
    path = path.resolve()
    return path == root or root in path.parents


def _snapshot_mp4(root: Path) -> dict[Path, tuple[int, int]]:
    snapshot: dict[Path, tuple[int, int]] = {}
    for path in sorted(root.rglob("*.mp4")):
        resolved = path.resolve()
        if not _inside(root, resolved) or not resolved.is_file():
            continue
        stat = resolved.stat()
        snapshot[resolved] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def _wait_for_one_new_mp4(
    root: Path,
    before: dict[Path, tuple[int, int]],
    *,
    timeout_seconds: float = 30.0,
) -> Path:
    deadline = time.monotonic() + timeout_seconds
    stable_path: Path | None = None
    stable_size = -1
    stable_checks = 0
    while time.monotonic() < deadline:
        after = _snapshot_mp4(root)
        changed = [path for path, state in after.items() if before.get(path) != state]
        if len(changed) > 1:
            names = ", ".join(str(path.relative_to(root)) for path in changed)
            raise AcpError(f"Grok Build produced multiple MP4 files for one prompt: {names}")
        if len(changed) == 1:
            path = changed[0]
            size = after[path][0]
            if size > 0 and path == stable_path and size == stable_size:
                stable_checks += 1
            else:
                stable_path = path
                stable_size = size
                stable_checks = 0
            if size > 0 and stable_checks >= 1:
                return path
        time.sleep(0.25)
    raise AcpError("Grok Build completed the turn without producing exactly one non-empty MP4")


class AcpClient:
    """Small synchronous JSON-RPC client for ``grok agent stdio``."""

    def __init__(
        self,
        command: list[str],
        cwd: Path,
        *,
        environment: dict[str, str] | None = None,
        transcript_path: Path | None = None,
        allowed_permission_tools: frozenset[str] = ALLOWED_MEDIA_TOOLS,
    ) -> None:
        self.command = list(command)
        self.cwd = cwd.resolve()
        self.transcript_path = transcript_path
        self._transcript_lock = threading.Lock()
        self._messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr: list[str] = []
        self._next_id = 1
        self.allowed_permission_tools = allowed_permission_tools
        self.permission_decisions: list[dict[str, str]] = []
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            self.command,
            cwd=str(self.cwd),
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        if self.process.stdin is None or self.process.stdout is None or self.process.stderr is None:
            raise AcpError("failed to open Grok Build ACP stdio pipes")
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _record(self, direction: str, message: Any) -> None:
        if self.transcript_path is None:
            return
        payload = {"at": _utc_now(), "direction": direction, "message": message}
        with self._transcript_lock:
            self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
            with self.transcript_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for raw in self.process.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self._messages.put({"_malformed": line})
                continue
            if isinstance(message, dict):
                self._record("received", message)
                self._messages.put(message)
        self._messages.put({"_eof": True})

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for raw in self.process.stderr:
            line = raw.rstrip()
            if line:
                self._stderr.append(line)
                self._record("stderr", line)

    def _write(self, message: dict[str, Any]) -> None:
        if self.process.poll() is not None:
            raise AcpError(self._process_failure("Grok Build ACP process exited"))
        assert self.process.stdin is not None
        self._record("sent", message)
        try:
            self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise AcpError(self._process_failure(f"failed writing to Grok Build ACP: {exc}")) from exc

    def _process_failure(self, prefix: str) -> str:
        detail = "\n".join(self._stderr[-20:]).strip()
        return f"{prefix}: {detail}" if detail else prefix

    def _handle_server_request(self, message: dict[str, Any]) -> None:
        if "id" not in message or not message.get("method"):
            return
        if message.get("method") == "session/request_permission":
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            tool_call = params.get("toolCall") if isinstance(params.get("toolCall"), dict) else {}
            tool_meta = tool_call.get("_meta") if isinstance(tool_call.get("_meta"), dict) else {}
            xai_tool = tool_meta.get("x.ai/tool") if isinstance(tool_meta.get("x.ai/tool"), dict) else {}
            tool_name = str(xai_tool.get("name") or tool_call.get("title") or "").strip()
            allowed = tool_name in self.allowed_permission_tools
            preferred_kinds = (
                ("allow_once", "allow_always") if allowed else ("reject_once", "reject_always")
            )
            options = params.get("options") if isinstance(params.get("options"), list) else []
            selected: dict[str, Any] | None = None
            for kind in preferred_kinds:
                selected = next(
                    (
                        option
                        for option in options
                        if isinstance(option, dict)
                        and option.get("kind") == kind
                        and option.get("optionId")
                    ),
                    None,
                )
                if selected is not None:
                    break
            if selected is None:
                result = {"outcome": {"outcome": "cancelled"}}
                option_id = "cancelled"
            else:
                option_id = str(selected["optionId"])
                result = {"outcome": {"outcome": "selected", "optionId": option_id}}
            self.permission_decisions.append(
                {
                    "tool": tool_name or "unknown",
                    "decision": "allow" if allowed and selected is not None else "reject",
                    "option_id": option_id,
                }
            )
            self._write(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": result,
                }
            )
            return
        self._write(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {
                    "code": -32601,
                    "message": f"client method is disabled: {message.get('method')}",
                },
            }
        )

    @staticmethod
    def _is_update(message: dict[str, Any]) -> bool:
        return message.get("method") == "session/update"

    def request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float,
        on_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AcpError(f"Grok Build ACP request timed out: {method}")
            try:
                message = self._messages.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                if self.process.poll() is not None:
                    raise AcpError(self._process_failure(f"Grok Build exited during {method}"))
                continue
            if message.get("_eof"):
                raise AcpError(self._process_failure(f"Grok Build closed stdout during {method}"))
            if message.get("_malformed"):
                raise AcpError(f"Grok Build emitted non-JSON ACP output: {message['_malformed']}")
            if self._is_update(message):
                if on_update:
                    on_update(message)
                continue
            if message.get("id") == request_id:
                if message.get("error"):
                    error = message["error"]
                    detail = error.get("message") if isinstance(error, dict) else str(error)
                    raise AcpError(f"Grok Build ACP {method} failed: {detail}")
                result = message.get("result")
                return result if isinstance(result, dict) else {}
            self._handle_server_request(message)

    def drain_updates(
        self,
        *,
        quiet_seconds: float = 0.5,
        on_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        deadline = time.monotonic() + quiet_seconds
        while time.monotonic() < deadline:
            try:
                message = self._messages.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                return
            if self._is_update(message):
                if on_update:
                    on_update(message)
                deadline = time.monotonic() + quiet_seconds
            elif not message.get("_eof") and not message.get("_malformed"):
                self._handle_server_request(message)

    def close(self) -> None:
        try:
            if self.process.stdin:
                self.process.stdin.close()
        except OSError:
            pass
        if self.process.poll() is None:
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        for stream in (self.process.stdout, self.process.stderr):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass
        self._stdout_thread.join(timeout=1)
        self._stderr_thread.join(timeout=1)


def _auth_method_ids(init: dict[str, Any]) -> set[str]:
    methods: set[str] = set()
    for item in init.get("authMethods") or []:
        if isinstance(item, dict) and item.get("id"):
            methods.add(str(item["id"]))
        elif isinstance(item, str):
            methods.add(item)
    return methods


def _grok_home(environment: dict[str, str] | None) -> Path:
    env = environment or os.environ
    configured = env.get("GROK_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    home_raw = env.get("USERPROFILE") or env.get("HOME")
    home = Path(home_raw).expanduser().resolve() if home_raw else Path.home().resolve()
    return home / ".grok"


def _zdr_video_storage_configured(environment: dict[str, str] | None) -> bool:
    path = _grok_home(environment) / "managed_config.toml"
    if not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            config = tomllib.load(handle)
    except (OSError, ValueError):
        return False
    tools = config.get("tools") if isinstance(config, dict) else None
    storage = tools.get("zdr_video_output_s3") if isinstance(tools, dict) else None
    read_write = storage.get("read_write") if isinstance(storage, dict) else None
    return bool(
        isinstance(storage, dict)
        and all(str(storage.get(key) or "").strip() for key in ("bucket", "endpoint", "region"))
        and isinstance(read_write, dict)
        and str(read_write.get("access_key_id") or "").strip()
        and str(read_write.get("secret_access_key") or "").strip()
    )


def _require_video_retention_route(
    authentication: dict[str, Any],
    environment: dict[str, str] | None,
) -> None:
    meta = authentication.get("_meta") if isinstance(authentication.get("_meta"), dict) else {}
    zdr_active = meta.get("is_zdr") is True or meta.get("coding_data_retention_opt_out") is True
    if zdr_active and not _zdr_video_storage_configured(environment):
        raise AcpError(
            "Grok Build video generation is blocked by the cached account's privacy/ZDR setting. "
            "Either turn off `/privacy` in an interactive Grok Build session or configure "
            "user-hosted ZDR video storage in ~/.grok/managed_config.toml; this skill will "
            "not change privacy settings or provision storage automatically."
        )


def _session_update_collector(
    session_id: str,
    chunks: list[str],
    tool_failures: list[str],
    tool_inventory: set[str],
    *,
    session_media_root: Path | None = None,
    image_mirror_dir: Path | None = None,
    mirrored_paths: list[Path] | None = None,
) -> Callable[[dict[str, Any]], None]:
    def collect(message: dict[str, Any]) -> None:
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        update_session = str(params.get("sessionId") or params.get("session_id") or "")
        if session_id and update_session and update_session != session_id:
            return
        update = params.get("update") if isinstance(params.get("update"), dict) else {}
        update_kind = update.get("sessionUpdate")
        if update_kind == "agent_message_chunk":
            content = update.get("content") if isinstance(update.get("content"), dict) else {}
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
        elif update_kind == "available_commands_update":
            update_meta = update.get("_meta") if isinstance(update.get("_meta"), dict) else {}
            tools = update_meta.get("tools") if isinstance(update_meta.get("tools"), list) else []
            tool_inventory.update(str(tool) for tool in tools if isinstance(tool, str))
        elif update_kind == "tool_call_update" and str(update.get("status") or "").lower() == "failed":
            for entry in update.get("content") or []:
                if not isinstance(entry, dict):
                    continue
                nested = entry.get("content") if isinstance(entry.get("content"), dict) else {}
                text = nested.get("text")
                if isinstance(text, str) and text.strip():
                    tool_failures.append(text.strip())
        elif update_kind == "tool_call_update" and str(update.get("status") or "").lower() == "completed":
            raw_output = update.get("rawOutput") if isinstance(update.get("rawOutput"), dict) else {}
            if (
                raw_output.get("type") == "ImageGen"
                and session_media_root is not None
                and image_mirror_dir is not None
            ):
                source_raw = raw_output.get("path")
                filename_raw = raw_output.get("filename")
                if not isinstance(source_raw, str) or not isinstance(filename_raw, str):
                    raise AcpError("image_gen completed without a filesystem path and filename")
                filename = Path(filename_raw).name
                if filename != filename_raw or not filename.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".webp")
                ):
                    raise AcpError(f"image_gen returned an unsafe filename: {filename_raw}")
                source = Path(source_raw).resolve()
                if not _inside(session_media_root, source) or not source.is_file():
                    raise AcpError(f"image_gen output escaped the exact Grok session: {source}")
                image_mirror_dir.mkdir(parents=True, exist_ok=True)
                destination = (image_mirror_dir / filename).resolve()
                if not _inside(image_mirror_dir, destination):
                    raise AcpError(f"image mirror path escaped the ACP scratch directory: {destination}")
                shutil.copy2(source, destination)
                if destination.stat().st_size <= 0:
                    raise AcpError(f"mirrored image is empty: {destination}")
                if mirrored_paths is not None and destination not in mirrored_paths:
                    mirrored_paths.append(destination)

    return collect


def _grok_session_root(
    transport_cwd: Path,
    session_id: str,
    environment: dict[str, str] | None,
) -> Path:
    env = environment or os.environ
    home_raw = env.get("USERPROFILE") or env.get("HOME")
    home = Path(home_raw).expanduser().resolve() if home_raw else Path.home().resolve()
    encoded_cwd = quote(str(transport_cwd.resolve()), safe="")
    return (home / ".grok" / "sessions" / encoded_cwd / session_id).resolve()


def _wait_for_session_root(path: Path, *, timeout_seconds: float = 10.0) -> Path:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_dir():
            return path.resolve()
        time.sleep(0.1)
    raise AcpError(f"Grok Build did not create its ACP session media directory: {path}")


def _validate_batch_shape(batch: dict[str, Any]) -> list[dict[str, Any]]:
    if batch.get("schema") != "grok_video_prompt_batch_v1":
        raise ValueError("prompt_batch must use schema grok_video_prompt_batch_v1")
    expected_format = {"duration_seconds": 6, "aspect_ratio": "9:16", "resolution": "720p"}
    if batch.get("format") != expected_format:
        raise ValueError("prompt_batch format must be 6 seconds, 9:16, 720p")
    items = batch.get("items")
    if not isinstance(items, list) or not items or batch.get("count") != len(items):
        raise ValueError("prompt_batch items/count are invalid")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"prompt_batch.items[{index}] must be an object")
        expected_id = f"prompt-{index + 1:03d}"
        if item.get("id") != expected_id or item.get("index") != index:
            raise ValueError(f"prompt_batch.items[{index}] order/id is invalid")
        if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
            raise ValueError(f"prompt_batch.items[{index}].prompt must be non-blank")
    return items


def build_grok_command(executable: str, workspace: Path, agent_profile: Path) -> list[str]:
    return [
        executable,
        "--no-auto-update",
        "--cwd",
        str(workspace),
        "--no-subagents",
        "--no-memory",
        "--disable-web-search",
        "agent",
        "--no-leader",
        "--always-approve",
        "--agent-profile",
        str(agent_profile.resolve()),
        "stdio",
    ]


def resolve_grok_executable() -> str:
    executable = shutil.which("grok") or shutil.which("grok.exe")
    if not executable:
        raise FileNotFoundError(
            "Grok Build CLI is not installed or is not on PATH. Install it, then run `grok login`."
        )
    return executable


def read_grok_version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    text = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0 or not text:
        raise AcpError(f"unable to read Grok Build version: {text or completed.returncode}")
    return text.splitlines()[0].strip()


def generate_batch(
    batch: dict[str, Any],
    attempt_dir: Path,
    *,
    command: list[str],
    grok_version: str,
    environment: dict[str, str] | None = None,
    prompt_timeout_seconds: float = 1800.0,
    output_wait_seconds: float = 30.0,
    transport_cwd: Path | None = None,
    media_root_resolver: Callable[[str], Path] | None = None,
) -> dict[str, Any]:
    items = _validate_batch_shape(batch)
    attempt_dir = attempt_dir.resolve()
    attempt_dir.mkdir(parents=True, exist_ok=False)
    canonical_dir = attempt_dir / "canonical"
    canonical_dir.mkdir()
    transport_cwd = (transport_cwd or attempt_dir).resolve()
    if not transport_cwd.is_dir():
        raise ValueError(f"ACP transport cwd does not exist: {transport_cwd}")
    transcript_path = attempt_dir / "acp-transcript.ndjson"
    client = AcpClient(command, transport_cwd, environment=environment, transcript_path=transcript_path)
    session_id = ""
    session_closed = False
    session_media_root: Path | None = None
    completed_ids: list[str] = []
    videos: list[dict[str, Any]] = []
    receipt_clips: list[dict[str, Any]] = []
    mirrored_paths: list[Path] = []
    try:
        init = client.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": False,
                },
            },
            timeout_seconds=30,
        )
        if "cached_token" not in _auth_method_ids(init):
            raise AcpError("cached Grok login is unavailable; run `grok login` before this skill")
        authentication = client.request(
            "authenticate",
            {"methodId": "cached_token", "_meta": {"headless": True}},
            timeout_seconds=60,
        )
        _require_video_retention_route(authentication, environment)
        inventory: set[str] = set()
        initial_chunks: list[str] = []
        initial_failures: list[str] = []
        inventory_collector = _session_update_collector(
            "",
            initial_chunks,
            initial_failures,
            inventory,
        )
        session = client.request(
            "session/new",
            {"cwd": str(transport_cwd), "mcpServers": []},
            timeout_seconds=60,
            on_update=inventory_collector,
        )
        session_id = str(session.get("sessionId") or "").strip()
        if not session_id:
            raise AcpError("Grok Build ACP session/new returned no sessionId")
        client.drain_updates(quiet_seconds=1.0, on_update=inventory_collector)
        missing_tools = sorted(ALLOWED_MEDIA_TOOLS - inventory)
        extra_tools = sorted(inventory - ALLOWED_MEDIA_TOOLS)
        if missing_tools:
            raise AcpError(f"Grok Build did not expose required media tools: {', '.join(missing_tools)}")
        if extra_tools:
            raise AcpError(
                "Grok Build did not honor the isolated media-tool allowlist; unexpected tools: "
                + ", ".join(extra_tools)
            )
        if media_root_resolver is not None:
            session_media_root = media_root_resolver(session_id).resolve()
        else:
            session_media_root = _grok_session_root(transport_cwd, session_id, environment)
        session_media_root = _wait_for_session_root(session_media_root)

        for item in items:
            before = _snapshot_mp4(session_media_root)
            chunks: list[str] = []
            tool_failures: list[str] = []
            turn_inventory: set[str] = set()
            collect = _session_update_collector(
                session_id,
                chunks,
                tool_failures,
                turn_inventory,
                session_media_root=session_media_root,
                image_mirror_dir=transport_cwd / "images",
                mirrored_paths=mirrored_paths,
            )
            command_text = PROMPT_TEMPLATE.format(prompt=item["prompt"])
            prompt_result = client.request(
                "session/prompt",
                {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": command_text}],
                },
                timeout_seconds=prompt_timeout_seconds,
                on_update=collect,
            )
            client.drain_updates(on_update=collect)
            stop_reason = str(prompt_result.get("stopReason") or "")
            if stop_reason.lower() in {"cancelled", "canceled"}:
                detail = "; ".join(tool_failures) or str(
                    prompt_result.get("cancellationContext") or "turn cancelled"
                )
                raise AcpError(f"Grok Build cancelled {item['id']}: {detail}")
            try:
                source = _wait_for_one_new_mp4(
                    session_media_root,
                    before,
                    timeout_seconds=output_wait_seconds,
                )
            except AcpError as exc:
                if tool_failures:
                    raise AcpError(
                        f"Grok Build media tool failed for {item['id']}: "
                        + "; ".join(tool_failures)
                    ) from exc
                raise
            if not _inside(session_media_root, source):
                raise AcpError(f"Grok Build output escaped its exact ACP session directory: {source}")
            canonical = canonical_dir / f"{item['id']}.mp4"
            shutil.copy2(source, canonical)
            if canonical.stat().st_size <= 0:
                raise AcpError(f"canonical video is empty: {canonical}")
            digest = _sha256(canonical)
            relative_source = source.relative_to(session_media_root).as_posix()
            videos.append(
                {
                    "id": item["id"],
                    "name": f"Grok Build clip {item['index'] + 1:03d}",
                    "path": str(canonical),
                    "index": item["index"],
                    "prompt": item["prompt"],
                }
            )
            receipt_clips.append(
                {
                    "id": item["id"],
                    "index": item["index"],
                    "source_prompt": item["prompt"],
                    "grok_command": command_text,
                    "source_path": relative_source,
                    "canonical_path": canonical.relative_to(attempt_dir).as_posix(),
                    "sha256": digest,
                    "bytes": canonical.stat().st_size,
                    "session_id": session_id,
                    "stop_reason": stop_reason,
                    "assistant_text": "".join(chunks).strip(),
                    "tool_failures": tool_failures,
                }
            )
            completed_ids.append(item["id"])

        client.request(
            "session/close",
            {"sessionId": session_id},
            timeout_seconds=30,
        )
        session_closed = True

        receipt = {
            "schema": "grok_video_batch_receipt_v1",
            "transport": "acp",
            "session_id": session_id,
            "grok_version": grok_version,
            "count": len(videos),
            "format": dict(batch["format"]),
            "attempt_dir": str(attempt_dir),
            "transport_cwd": str(transport_cwd),
            "session_media_root": str(session_media_root),
            "transcript_path": str(transcript_path),
            "clips": receipt_clips,
            "allowed_tools": sorted(ALLOWED_MEDIA_TOOLS),
            "permission_decisions": client.permission_decisions,
            "started_and_completed_in_one_process": True,
            "session_closed": session_closed,
            "completed_at": _utc_now(),
        }
        return {"videos": videos, "receipt": receipt}
    except Exception as exc:
        failure = {
            "schema": "grok_video_batch_failure_v1",
            "session_id": session_id,
            "completed_ids": completed_ids,
            "error": f"{type(exc).__name__}: {exc}",
            "failed_at": _utc_now(),
        }
        (attempt_dir / "failure.json").write_text(
            json.dumps(failure, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        raise
    finally:
        if session_id and not session_closed and client.process.poll() is None:
            try:
                client.request(
                    "session/close",
                    {"sessionId": session_id},
                    timeout_seconds=10,
                )
            except Exception:
                pass
        client.close()
        for mirrored in mirrored_paths:
            try:
                if _inside(transport_cwd, mirrored) and mirrored.is_file():
                    mirrored.unlink()
            except OSError:
                pass
        try:
            (transport_cwd / "images").rmdir()
        except OSError:
            pass


def run(
    input_data: dict[str, Any],
    draft: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    del draft
    batch = input_data.get("prompt_batch")
    if not isinstance(batch, dict):
        raise ValueError("grok_build_acp_video_batch needs prompt_batch")
    work_dir_raw = input_data.get("work_dir")
    if not isinstance(work_dir_raw, str) or not work_dir_raw.strip():
        raise ValueError("grok_build_acp_video_batch needs an internal work_dir")
    work_dir = Path(work_dir_raw).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    attempt = work_dir / f"attempt_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"

    executable = resolve_grok_executable()
    version = read_grok_version(executable)
    environment = dict(os.environ)
    environment.pop("XAI_API_KEY", None)
    transport_cwd = Path(tempfile.mkdtemp(prefix="m8m-grok-acp-")).resolve()
    agent_profile = Path(__file__).resolve().with_name("grok-video-agent.md")
    if not agent_profile.is_file():
        raise FileNotFoundError(f"Grok Build video agent profile is missing: {agent_profile}")
    command = build_grok_command(executable, transport_cwd, agent_profile)
    try:
        return generate_batch(
            batch,
            attempt,
            command=command,
            grok_version=version,
            environment=environment,
            transport_cwd=transport_cwd,
        )
    finally:
        try:
            transport_cwd.rmdir()
        except OSError:
            pass
