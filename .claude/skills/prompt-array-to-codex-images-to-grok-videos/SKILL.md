---
name: prompt-array-to-codex-images-to-grok-videos
description: Generate an ordered Codex ImageGen still array from editorial prompts, derive one image-grounded motion prompt per still, and create one ordered Grok Build MP4 per image through an M8M v4 workflow.
license: MIT
metadata:
  author: dse120071750
  version: "1.0.0"
---

# Prompt array to Codex images to Grok videos

Run the repo-local M8M flow
`prompt_array_to_codex_images_to_grok_videos_v1`. It accepts exactly one
non-empty `prompts` array. Preserve every prompt verbatim and preserve source
order.

The milestones are:

1. `prompt_batch_ready` freezes stable IDs, Codex built-in ImageGen, vertical
   9:16 stills, and 6-second 720p Grok masters.
2. `codex_images_generated_frozen` uses a fresh isolated worker and one
   built-in `image_gen` call per prompt. Its deterministic tools import only
   current-run generated images and freeze dimensions, byte counts, checksums,
   and ordered image members.
3. `image_video_prompts_frozen` uses another fresh isolated worker. It calls
   `view_image` on every frozen still and writes one bold three-second forward
   motion prompt per still without exposing its analysis.
4. `grok_videos_generated_frozen` uses one persistent, cached-login Grok Build
   ACP process and session. It exposes only `image_to_video`, creates a
   six-second reverse master from each exact still, and uses repository-local
   FFmpeg to reverse and accelerate it into a three-second forward clip.

Use M8M Harness Builder 2.0's `scripts/run_flow.py` with this repository as
`--codebase`. Start a fresh cache-off run. Whenever the runtime returns
`ACTION_REQUIRED`, launch a fresh no-history worker from the exact
`context_capsule_path`. The worker may read only `allowed_files` and write only
`write_file`. Resume only the exact same run with the resulting draft.

For image generation, use Codex built-in `image_gen` exactly once per item.
Never use an ImageGen CLI, an image REST API, an earlier image, or a combined
multi-image call.

For motion prompts, call `view_image` on every allowed frozen still in source
order. Keep analysis private and write only the schema-required draft.

Grok Build must already be installed and authenticated with `grok login`.
Require privacy off or complete user-hosted ZDR video storage. Never install or
authenticate Grok, change privacy, provision storage, call the xAI REST API,
generate replacement images, use another provider, or reuse prior clips.

Any failed item invalidates the current milestone. Do not select or publish a
partial batch.

After `COMPLETE`, run `python scripts/export_results.py <exact-run-dir>` or read
the chosen image members, `video_prompts` member, and chosen video members in
source order. Return only the resulting JSON array. Do not return attempt
paths, generated-images source paths, ACP transcripts, judge receipts, Markdown,
or commentary.

- flow: `flowsteps/flows/prompt_array_to_codex_images_to_grok_videos_v1/`
- chart: `flowsteps/flows/prompt_array_to_codex_images_to_grok_videos_v1/planning/m8m-flowchart.md`
- Grok ACP tool: `flowsteps/tools/grok_build_acp_image_video_batch/`
