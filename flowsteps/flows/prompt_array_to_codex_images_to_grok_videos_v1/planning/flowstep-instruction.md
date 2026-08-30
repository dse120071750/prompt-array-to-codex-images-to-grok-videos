<!-- flowstep_instruction_v1 -->
# FlowStep instruction: prompt_array_to_codex_images_to_grok_videos_v1

This file is the skill instruction. Each section is a milestone.
A milestone input schema is the previous milestone output schema.
Each milestone declares named output ports: FlowSteps refine candidates, the judge commits one chosen bundle, and only that bundle is downstream-visible.
Mark DONE only after the judge-approved current result is materialized as chosen-output.json.
FlowSteps inside a milestone are a guide: prefer one tool each, in table order.
The tool is optional. If it fails, recover like a normal agent. Do not skip required named outputs.

- harness: `<repo>/flowsteps/flows/prompt_array_to_codex_images_to_grok_videos_v1`
- flow_id: `prompt_array_to_codex_images_to_grok_videos_v1`
- final_payload: `grok_image_video_batch_v1` from `grok_videos_generated_frozen`
- updated_at: 2026-08-30T15:41:43Z

## Run

```powershell
python <builder>/scripts/run_flow.py --codebase <repo> --flow-id prompt_array_to_codex_images_to_grok_videos_v1 --run-dir <run-dir> --request <request.json>
```

If a milestone returns ACTION_REQUIRED, write only the frozen draft and advance.

## Tool vs intelligence

Schema: `tool_vs_intelligence_table_v1`.

| id | class | test | why |
| --- | --- | --- | --- |
| `prepare_visual_prompt_batch` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `codex_images_generated_frozen` | `intelligence` | fails at least one of the four tests; no fixture without a model | The built-in Codex ImageGen tool must be called once per editorial prompt; this action cannot be performed by deterministic local Python. |
| `freeze_codex_image_batch` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `codex_images_generated_judge` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `image_video_prompts_frozen` | `intelligence` | fails at least one of the four tests; no fixture without a model | Object-specific animation must be derived from private visual inspection of each frozen image. |
| `image_video_prompts_judge` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `grok_build_acp_image_video_batch` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `validate_grok_image_video_batch` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `grok_image_videos_generated_judge` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |

## Milestones

The M8M flowchart is `planning/m8m-flowchart.md` plus `planning/m8m-flowchart.jpg`.
The JPEG is rewritten on generate and on every step edit. It is the portable audit copy.

## Toolbox plan

Tools on each proposed milestone. **Existing toolbox** = already in
`<repo>/flowsteps/tools/` or an M8M seed. **Promote from a skill script** =
skill-private Python becomes that tool. **Generate new** = builder should
develop this tool; a stub is a successful sketch.

| Milestone | Intelligence | Existing toolbox | Promote from a skill script | Generate new |
| --- | --- | --- | --- | --- |
| `prompt_batch_ready` | `none` | `prepare_visual_prompt_batch` | — | — |
| `codex_images_generated_frozen` | `completion` | `freeze_codex_image_batch`<br>`codex_images_generated_judge` | — | — |
| `image_video_prompts_frozen` | `completion` | `image_video_prompts_judge` | — | — |
| `grok_videos_generated_frozen` | `none` | `grok_build_acp_image_video_batch`<br>`validate_grok_image_video_batch`<br>`grok_image_videos_generated_judge` | — | — |

## Toolbox

- `prepare_visual_prompt_batch` — `flowsteps/tools/prepare_visual_prompt_batch/tool.py`
- `freeze_codex_image_batch` — `flowsteps/tools/freeze_codex_image_batch/tool.py`
- `codex_images_generated_judge` — `flowsteps/tools/codex_images_generated_judge/tool.py`
- `image_video_prompts_judge` — `flowsteps/tools/image_video_prompts_judge/tool.py`
- `grok_build_acp_image_video_batch` — `flowsteps/tools/grok_build_acp_image_video_batch/tool.py`
- `validate_grok_image_video_batch` — `flowsteps/tools/validate_grok_image_video_batch/tool.py`
- `grok_image_videos_generated_judge` — `flowsteps/tools/grok_image_videos_generated_judge/tool.py`

## Teaching contracts

Same rule as tools. These live on the flow, not in `~/.codex/skills` or `~/.claude/skills`.

- `references/codex_images_generated_frozen.md`
- `references/grok_videos_generated_frozen.md`
- `references/image_video_prompts_frozen.md`
- `references/prompt_batch_ready.md`

## Milestone index


| # | Step | Class | Handler | Model | Why model | Inputs | Output contract | Output schema |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `prompt_batch_ready` | `tool` | `milestones/prompt_batch_ready/assemble.py` | `none` | none | request=user.request | `visual_prompt_batch_v1` | `schemas/prompt_batch_ready_v1.json` |
| 2 | `codex_images_generated_frozen` | `intelligence` | `milestones/codex_images_generated_frozen/assemble.py` | `completion` | The built-in Codex ImageGen tool must be called once per editorial prompt; this action cannot be performed by deterministic local Python. | prompt_batch={'from': 'prompt_batch_ready.visual_prompt_batch_v1', 'output': 'batch'} | `codex_image_batch_v1` | `schemas/codex_images_generated_frozen_v1.json` |
| 3 | `image_video_prompts_frozen` | `intelligence` | `milestones/image_video_prompts_frozen/assemble.py` | `completion` | Object-specific animation must be derived from private visual inspection of each frozen image. | images={'from': 'codex_images_generated_frozen.codex_image_batch_v1', 'output': 'images'}, image_manifest={'from': 'codex_images_generated_frozen.codex_image_batch_v1', 'output': 'manifest'} | `image_video_prompt_batch_v1` | `schemas/image_video_prompts_frozen_v1.json` |
| 4 | `grok_videos_generated_frozen` | `tool` | `milestones/grok_videos_generated_frozen/assemble.py` | `none` | none | prompt_batch={'from': 'prompt_batch_ready.visual_prompt_batch_v1', 'output': 'batch'}, images={'from': 'codex_images_generated_frozen.codex_image_batch_v1', 'output': 'images'}, image_manifest={'from': 'codex_images_generated_frozen.codex_image_batch_v1', 'output': 'manifest'}, video_prompts={'from': 'image_video_prompts_frozen.image_video_prompt_batch_v1', 'output': 'video_prompts'}, video_prompt_manifest={'from': 'image_video_prompts_frozen.image_video_prompt_batch_v1', 'output': 'manifest'} | `grok_image_video_batch_v1` | `schemas/grok_videos_generated_frozen_v1.json` |

This table is generated from the flow YAML. The Python tool and schemas are the runtime.

## Steps

### `prompt_batch_ready`
- status: DONE
- order: 1
- class: `tool`
- intelligence: `none`
- assemble: `milestones/prompt_batch_ready/assemble.py`
- toolbox: `prepare_visual_prompt_batch`
- flowsteps (guide): `prepare_visual_prompt_batch`→`prepare_visual_prompt_batch`
- test: `milestones/prompt_batch_ready/tests/test_assemble.py`
- model: `none`
- model_justification: none
- inputs: request=user.request
- input_schema: `milestones/prompt_batch_ready/input.schema.json`
- output_schema: `schemas/prompt_batch_ready_v1.json`
- output_contract: `visual_prompt_batch_v1`
- expected_return: `{"outputs": "object"}`

### `codex_images_generated_frozen`
- status: DONE
- order: 2
- class: `intelligence`
- intelligence: `completion`
- assemble: `milestones/codex_images_generated_frozen/assemble.py`
- toolbox: `freeze_codex_image_batch`, `codex_images_generated_judge`
- flowsteps (guide): `generate_with_codex_builtin_imagegen`→`—`, `freeze_codex_image_batch`→`freeze_codex_image_batch`, `judge_codex_image_batch`→`codex_images_generated_judge`
- test: `milestones/codex_images_generated_frozen/tests/test_assemble.py`
- model: `completion`
- model_justification: The built-in Codex ImageGen tool must be called once per editorial prompt; this action cannot be performed by deterministic local Python.
- inputs: prompt_batch={'from': 'prompt_batch_ready.visual_prompt_batch_v1', 'output': 'batch'}
- input_schema: `milestones/codex_images_generated_frozen/input.schema.json`
- output_schema: `schemas/codex_images_generated_frozen_v1.json`
- output_contract: `codex_image_batch_v1`
- expected_return: `{"outputs": "object", "receipt": "object"}`
- draft_schema: `milestones/codex_images_generated_frozen/draft.schema.json`

### `image_video_prompts_frozen`
- status: DONE
- order: 3
- class: `intelligence`
- intelligence: `completion`
- assemble: `milestones/image_video_prompts_frozen/assemble.py`
- toolbox: `image_video_prompts_judge`
- flowsteps (guide): `inspect_frozen_images`→`—`, `construct_image_video_prompts`→`—`, `judge_image_video_prompts`→`image_video_prompts_judge`
- test: `milestones/image_video_prompts_frozen/tests/test_assemble.py`
- model: `completion`
- model_justification: Object-specific animation must be derived from private visual inspection of each frozen image.
- inputs: images={'from': 'codex_images_generated_frozen.codex_image_batch_v1', 'output': 'images'}, image_manifest={'from': 'codex_images_generated_frozen.codex_image_batch_v1', 'output': 'manifest'}
- input_schema: `milestones/image_video_prompts_frozen/input.schema.json`
- output_schema: `schemas/image_video_prompts_frozen_v1.json`
- output_contract: `image_video_prompt_batch_v1`
- expected_return: `{"outputs": "object", "receipt": "object"}`
- draft_schema: `milestones/image_video_prompts_frozen/draft.schema.json`

### `grok_videos_generated_frozen`
- status: DONE
- order: 4
- class: `tool`
- intelligence: `none`
- assemble: `milestones/grok_videos_generated_frozen/assemble.py`
- toolbox: `grok_build_acp_image_video_batch`, `validate_grok_image_video_batch`, `grok_image_videos_generated_judge`
- flowsteps (guide): `run_persistent_grok_image_video_batch`→`grok_build_acp_image_video_batch`, `validate_grok_image_video_batch`→`validate_grok_image_video_batch`, `judge_grok_image_video_batch`→`grok_image_videos_generated_judge`
- test: `milestones/grok_videos_generated_frozen/tests/test_assemble.py`
- model: `none`
- model_justification: none
- inputs: prompt_batch={'from': 'prompt_batch_ready.visual_prompt_batch_v1', 'output': 'batch'}, images={'from': 'codex_images_generated_frozen.codex_image_batch_v1', 'output': 'images'}, image_manifest={'from': 'codex_images_generated_frozen.codex_image_batch_v1', 'output': 'manifest'}, video_prompts={'from': 'image_video_prompts_frozen.image_video_prompt_batch_v1', 'output': 'video_prompts'}, video_prompt_manifest={'from': 'image_video_prompts_frozen.image_video_prompt_batch_v1', 'output': 'manifest'}
- input_schema: `milestones/grok_videos_generated_frozen/input.schema.json`
- output_schema: `schemas/grok_videos_generated_frozen_v1.json`
- output_contract: `grok_image_video_batch_v1`
- expected_return: `{"outputs": "object", "receipt": "object"}`

After a step's tool, schemas, and test are real, mark it DONE.
Do not start the next step while the current step is PENDING.
