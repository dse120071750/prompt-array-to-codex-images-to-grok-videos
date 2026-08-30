"""Generate videos from frozen images in one persistent Grok Build ACP session.

There is intentionally no HTTP client, xAI API key, or video REST endpoint in
this module. The locally installed Grok Build process owns media generation.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ALLOWED_MEDIA_TOOLS = frozenset({"image_to_video"})
FINAL_FORMAT = {
    "duration_seconds": 3,
    "aspect_ratio": "9:16",
    "resolution": "720p",
    "grok_master_duration_seconds": 6,
    "temporal_transform": "reverse_and_2x",
}


def _base() -> Any:
    path = Path(__file__).resolve().parents[1] / "grok_build_acp_video_batch" / "tool.py"
    spec = importlib.util.spec_from_file_location("m8m_grok_acp_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shared Grok ACP transport: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inside(root: Path, path: Path) -> bool:
    root = root.resolve()
    path = path.resolve()
    return path == root or root in path.parents


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_inputs(
    prompt_batch: dict[str, Any],
    images: list[dict[str, Any]],
    image_manifest: dict[str, Any],
    video_prompts: dict[str, Any],
    run_dir: Path,
) -> list[dict[str, Any]]:
    if prompt_batch.get("schema") != "visual_prompt_batch_v1":
        raise ValueError("prompt_batch must use visual_prompt_batch_v1")
    if prompt_batch.get("video") != {"duration_seconds": 6, "aspect_ratio": "9:16", "resolution": "720p"}:
        raise ValueError("video format must remain 6 seconds, 9:16, and 720p")
    prompt_items = prompt_batch.get("items")
    if not isinstance(prompt_items, list) or not prompt_items or prompt_batch.get("count") != len(prompt_items):
        raise ValueError("prompt_batch items/count are invalid")
    manifest_items = image_manifest.get("items") if isinstance(image_manifest.get("items"), list) else []
    if image_manifest.get("schema") != "codex_image_batch_v1":
        raise ValueError("image manifest must use codex_image_batch_v1")
    if image_manifest.get("count") != len(images) or len(manifest_items) != len(images) or len(images) != len(prompt_items):
        raise ValueError("frozen image count does not match prompts")
    if video_prompts.get("schema") != "image_video_prompt_batch_v1":
        raise ValueError("video_prompts must use image_video_prompt_batch_v1")
    motion_items = video_prompts.get("items")
    if not isinstance(motion_items, list) or video_prompts.get("count") != len(motion_items):
        raise ValueError("video prompt items/count are invalid")
    if video_prompts.get("format") != FINAL_FORMAT:
        raise ValueError("motion prompt format is not frozen")
    if len(motion_items) != len(images):
        raise ValueError("motion prompt count does not match images")

    combined: list[dict[str, Any]] = []
    for index, (source_prompt, image, manifest_item, motion) in enumerate(zip(prompt_items, images, manifest_items, motion_items)):
        expected_id = f"prompt-{index + 1:03d}"
        if not all(isinstance(item, dict) for item in (source_prompt, image, manifest_item, motion)):
            raise ValueError(f"batch item {index} is malformed")
        if {source_prompt.get("id"), image.get("id"), motion.get("id")} != {expected_id}:
            raise ValueError(f"batch item {index} stable ID mismatch")
        if manifest_item.get("id") != f"prompt_{index + 1:03d}" or manifest_item.get("stable_id") != expected_id:
            raise ValueError(f"batch item {index} frozen manifest ID mismatch")
        if source_prompt.get("index") != index or image.get("index") != index or motion.get("index") != index:
            raise ValueError(f"batch item {index} numeric order mismatch")
        if manifest_item.get("index") != index or manifest_item.get("sha256") != image.get("sha256"):
            raise ValueError(f"batch item {index} frozen manifest binding mismatch")
        if image.get("source_prompt") != source_prompt.get("prompt") or motion.get("source_prompt") != source_prompt.get("prompt"):
            raise ValueError(f"batch item {index} source prompt mismatch")
        path_raw = image.get("path")
        if not isinstance(path_raw, str) or not path_raw:
            raise ValueError(f"batch item {index} has no source image path")
        image_path = Path(path_raw).resolve()
        if not _inside(run_dir, image_path) or not image_path.is_file():
            raise ValueError(f"batch item {index} source image escaped the current M8M run")
        digest = _sha256(image_path)
        if image.get("sha256") != digest or motion.get("source_image_sha256") != digest:
            raise ValueError(f"batch item {index} source image checksum changed")
        if Path(str(motion.get("source_image_path") or "")).resolve() != image_path:
            raise ValueError(f"batch item {index} motion prompt points to another image")
        video_prompt = motion.get("video_prompt")
        if not isinstance(video_prompt, str) or not video_prompt.strip():
            raise ValueError(f"batch item {index} has no motion prompt")
        combined.append({
            "id": expected_id,
            "index": index,
            "source_prompt": source_prompt["prompt"],
            "image_path": image_path,
            "image_sha256": digest,
            "video_prompt": video_prompt,
        })
    return combined


def _reverse_generation_prompt(video_prompt: str) -> str:
    return (
        "The supplied source image is the exact completed final still of the forward animation "
        "described below. Generate a 6-second reverse-motion master. Keep the supplied image "
        "perfectly still and unchanged for the first 1 second. During the remaining 5 seconds, "
        "perform the exact temporal reverse of the forward action: disassemble, withdraw, or move "
        "the described elements outward so that reversing this master makes the bold action enter "
        "and resolve precisely into the supplied image. Preserve the source composition, subjects, "
        "object count, palette, materials, textures, and background during the initial hold. Use a "
        "locked camera, one continuous shot, decisive large travel, and no text, letters, watermark, "
        "UI, 3D CGI, or photoreal environment.\n\nFORWARD_ACTION_TO_REVERSE:\n"
        + video_prompt
    )


def _command_text(relative_image: str, video_prompt: str) -> tuple[str, str]:
    reverse_prompt = _reverse_generation_prompt(video_prompt)
    return (
        "Create exactly one video from the existing source image below. Call image_to_video "
        "exactly once and no other tool. Use these arguments exactly:\n"
        f'image: "{relative_image}"\n'
        "duration: 6\n"
        'resolution_name: "720p"\n'
        "prompt: the complete text between REVERSE_MASTER_PROMPT_BEGIN and REVERSE_MASTER_PROMPT_END, "
        "verbatim and without the boundary labels. Do not generate or edit an image, do not "
        "replace the source frame, and do not add a second call.\n\n"
        "REVERSE_MASTER_PROMPT_BEGIN\n"
        + reverse_prompt
        + "\nREVERSE_MASTER_PROMPT_END",
        reverse_prompt,
    )


def resolve_ffmpeg_command() -> list[str]:
    codebase = Path(__file__).resolve().parents[3]
    candidates = [
        codebase / "node_modules" / "ffmpeg-static" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"),
        codebase / "node_modules" / "@remotion" / "compositor-win32-x64-msvc" / "ffmpeg.exe",
    ]
    executable = next((path for path in candidates if path.is_file()), None)
    if executable is None:
        raise FileNotFoundError("repository-bundled ffmpeg executable was not found")
    return [str(executable.resolve())]


def render_forward_three_seconds(master: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        *resolve_ffmpeg_command(),
        "-y",
        "-v", "error",
        "-i", str(master),
        "-an",
        "-vf", "reverse,setpts=0.5*PTS",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(destination),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0 or not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError("failed to reverse and accelerate Grok master: " + (completed.stderr or "unknown ffmpeg error").strip())


def generate_batch(
    prompt_batch: dict[str, Any],
    images: list[dict[str, Any]],
    image_manifest: dict[str, Any],
    video_prompts: dict[str, Any],
    attempt_dir: Path,
    *,
    run_dir: Path,
    command: list[str],
    grok_version: str,
    environment: dict[str, str] | None = None,
    prompt_timeout_seconds: float = 1800.0,
    output_wait_seconds: float = 30.0,
    transport_cwd: Path,
    media_root_resolver: Callable[[str], Path] | None = None,
    client_factory: Callable[..., Any] | None = None,
    video_postprocessor: Callable[[Path, Path], None] | None = None,
) -> dict[str, Any]:
    base = _base()
    items = _validate_inputs(prompt_batch, images, image_manifest, video_prompts, run_dir.resolve())
    attempt_dir = attempt_dir.resolve()
    attempt_dir.mkdir(parents=True, exist_ok=False)
    canonical_dir = attempt_dir / "canonical"
    canonical_dir.mkdir()
    masters_dir = attempt_dir / "masters"
    masters_dir.mkdir()
    transport_cwd = transport_cwd.resolve()
    if not transport_cwd.is_dir():
        raise ValueError(f"ACP transport cwd does not exist: {transport_cwd}")
    transport_images = transport_cwd / "images"
    transport_images.mkdir(parents=True, exist_ok=False)
    copied_inputs: list[Path] = []
    for item in items:
        suffix = item["image_path"].suffix.lower()
        destination = (transport_images / f"{item['id']}{suffix}").resolve()
        if not _inside(transport_images, destination):
            raise ValueError("transport image escaped ACP scratch directory")
        shutil.copy2(item["image_path"], destination)
        if _sha256(destination) != item["image_sha256"]:
            raise ValueError(f"transport image checksum changed for {item['id']}")
        item["transport_image"] = destination
        item["relative_image"] = destination.relative_to(transport_cwd).as_posix()
        copied_inputs.append(destination)

    transcript_path = attempt_dir / "acp-transcript.ndjson"
    factory = client_factory or base.AcpClient
    client = factory(
        command,
        transport_cwd,
        environment=environment,
        transcript_path=transcript_path,
        allowed_permission_tools=ALLOWED_MEDIA_TOOLS,
    )
    session_id = ""
    session_closed = False
    session_media_root: Path | None = None
    completed_ids: list[str] = []
    videos: list[dict[str, Any]] = []
    receipt_clips: list[dict[str, Any]] = []
    try:
        init = client.request(
            "initialize",
            {"protocolVersion": 1, "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False}},
            timeout_seconds=30,
        )
        if "cached_token" not in base._auth_method_ids(init):
            raise base.AcpError("cached Grok login is unavailable; run `grok login` before this skill")
        authentication = client.request(
            "authenticate",
            {"methodId": "cached_token", "_meta": {"headless": True}},
            timeout_seconds=60,
        )
        base._require_video_retention_route(authentication, environment)
        inventory: set[str] = set()
        initial_chunks: list[str] = []
        initial_failures: list[str] = []
        inventory_collector = base._session_update_collector("", initial_chunks, initial_failures, inventory)
        session = client.request(
            "session/new",
            {"cwd": str(transport_cwd), "mcpServers": []},
            timeout_seconds=60,
            on_update=inventory_collector,
        )
        session_id = str(session.get("sessionId") or "").strip()
        if not session_id:
            raise base.AcpError("Grok Build ACP session/new returned no sessionId")
        client.drain_updates(quiet_seconds=1.0, on_update=inventory_collector)
        missing = sorted(ALLOWED_MEDIA_TOOLS - inventory)
        extra = sorted(inventory - ALLOWED_MEDIA_TOOLS)
        if missing:
            raise base.AcpError("Grok Build did not expose image_to_video")
        if extra:
            raise base.AcpError("Grok Build did not honor the image-to-video-only allowlist: " + ", ".join(extra))
        session_media_root = (
            media_root_resolver(session_id).resolve()
            if media_root_resolver is not None
            else base._grok_session_root(transport_cwd, session_id, environment)
        )
        session_media_root = base._wait_for_session_root(session_media_root)

        for item in items:
            before = base._snapshot_mp4(session_media_root)
            chunks: list[str] = []
            tool_failures: list[str] = []
            turn_inventory: set[str] = set()
            collect = base._session_update_collector(session_id, chunks, tool_failures, turn_inventory)
            command_text, reverse_prompt = _command_text(item["relative_image"], item["video_prompt"])
            result = client.request(
                "session/prompt",
                {"sessionId": session_id, "prompt": [{"type": "text", "text": command_text}]},
                timeout_seconds=prompt_timeout_seconds,
                on_update=collect,
            )
            client.drain_updates(on_update=collect)
            stop_reason = str(result.get("stopReason") or "")
            if stop_reason.lower() in {"cancelled", "canceled"}:
                detail = "; ".join(tool_failures) or str(result.get("cancellationContext") or "turn cancelled")
                raise base.AcpError(f"Grok Build cancelled {item['id']}: {detail}")
            try:
                source = base._wait_for_one_new_mp4(session_media_root, before, timeout_seconds=output_wait_seconds)
            except base.AcpError as exc:
                if tool_failures:
                    raise base.AcpError(f"Grok Build image_to_video failed for {item['id']}: " + "; ".join(tool_failures)) from exc
                raise
            if not _inside(session_media_root, source):
                raise base.AcpError(f"Grok Build output escaped its exact ACP session directory: {source}")
            master = masters_dir / f"{item['id']}.mp4"
            shutil.copy2(source, master)
            if master.stat().st_size <= 0:
                raise base.AcpError(f"Grok reverse master is empty: {master}")
            canonical = canonical_dir / f"{item['id']}.mp4"
            (video_postprocessor or render_forward_three_seconds)(master, canonical)
            if canonical.stat().st_size <= 0:
                raise base.AcpError(f"canonical video is empty: {canonical}")
            digest = _sha256(canonical)
            videos.append({
                "id": item["id"],
                "name": f"Grok Build image-derived clip {item['index'] + 1:03d}",
                "path": str(canonical),
                "index": item["index"],
                "source_prompt": item["source_prompt"],
                "source_image_path": str(item["image_path"]),
                "source_image_sha256": item["image_sha256"],
                "video_prompt": item["video_prompt"],
            })
            receipt_clips.append({
                "id": item["id"],
                "index": item["index"],
                "source_prompt": item["source_prompt"],
                "source_image_path": str(item["image_path"]),
                "source_image_sha256": item["image_sha256"],
                "transport_image_path": item["relative_image"],
                "video_prompt": item["video_prompt"],
                "grok_generation_prompt": reverse_prompt,
                "grok_command": command_text,
                "source_video_path": source.relative_to(session_media_root).as_posix(),
                "master_path": master.relative_to(attempt_dir).as_posix(),
                "master_sha256": _sha256(master),
                "master_bytes": master.stat().st_size,
                "canonical_path": canonical.relative_to(attempt_dir).as_posix(),
                "temporal_transform": "reverse_and_2x",
                "sha256": digest,
                "bytes": canonical.stat().st_size,
                "session_id": session_id,
                "stop_reason": stop_reason,
                "assistant_text": "".join(chunks).strip(),
                "tool_failures": tool_failures,
            })
            completed_ids.append(item["id"])

        client.request("session/close", {"sessionId": session_id}, timeout_seconds=30)
        session_closed = True
        receipt = {
            "schema": "grok_image_video_batch_receipt_v1",
            "transport": "acp",
            "session_id": session_id,
            "grok_version": grok_version,
            "count": len(videos),
            "format": dict(FINAL_FORMAT),
            "attempt_dir": str(attempt_dir),
            "transport_cwd": str(transport_cwd),
            "session_media_root": str(session_media_root),
            "transcript_path": str(transcript_path),
            "clips": receipt_clips,
            "allowed_tools": sorted(ALLOWED_MEDIA_TOOLS),
            "permission_decisions": getattr(client, "permission_decisions", []),
            "started_and_completed_in_one_process": True,
            "session_closed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        return {"videos": videos, "receipt": receipt}
    except Exception as exc:
        failure = {
            "schema": "grok_image_video_batch_failure_v1",
            "session_id": session_id,
            "completed_ids": completed_ids,
            "error": f"{type(exc).__name__}: {exc}",
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        (attempt_dir / "failure.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise
    finally:
        if session_id and not session_closed and getattr(client, "process", None) is not None and client.process.poll() is None:
            try:
                client.request("session/close", {"sessionId": session_id}, timeout_seconds=10)
            except Exception:
                pass
        client.close()
        for path in copied_inputs:
            try:
                if _inside(transport_images, path) and path.is_file():
                    path.unlink()
            except OSError:
                pass
        try:
            transport_images.rmdir()
        except OSError:
            pass


def run(input_data: dict[str, Any], draft: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    del draft
    required = ("prompt_batch", "images", "image_manifest", "video_prompts", "work_dir", "run_dir")
    if any(key not in input_data for key in required):
        raise ValueError("grok_build_acp_image_video_batch needs prompt_batch, images, image_manifest, video_prompts, work_dir, and run_dir")
    if not isinstance(input_data["images"], list):
        raise ValueError("images must be an ordered array")
    work_dir = Path(str(input_data["work_dir"])).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    attempt = work_dir / f"attempt_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    base = _base()
    executable = base.resolve_grok_executable()
    version = base.read_grok_version(executable)
    environment = dict(os.environ)
    environment.pop("XAI_API_KEY", None)
    transport_cwd = Path(tempfile.mkdtemp(prefix="m8m-grok-image-video-")).resolve()
    profile = Path(__file__).resolve().with_name("grok-image-video-agent.md")
    if not profile.is_file():
        raise FileNotFoundError(f"Grok Build image-to-video agent profile is missing: {profile}")
    command = base.build_grok_command(executable, transport_cwd, profile)
    try:
        return generate_batch(
            input_data["prompt_batch"],
            input_data["images"],
            input_data["image_manifest"],
            input_data["video_prompts"],
            attempt,
            run_dir=Path(str(input_data["run_dir"])).resolve(),
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
