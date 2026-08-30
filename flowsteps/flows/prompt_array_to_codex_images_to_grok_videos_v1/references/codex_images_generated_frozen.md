# Codex images generated and frozen

Use the built-in Codex `image_gen` tool, never an image API or CLI. Call it
exactly once for each frozen source prompt, sequentially in source order. Each
call creates one final project-bound still. Preserve the already detailed
source prompt verbatim; do not add characters, objects, brands, text, story
beats, or alternate art direction. Require a vertical 9:16 raster image and no
watermark.

The worker must return only the draft JSON object required by the draft schema.
Every item maps its stable ID, numeric index, exact source prompt, exact prompt
sent to ImageGen, and the absolute generated file path reported by the built-in
tool. Do not copy files, use a CLI, use an API key, return previews, or reuse an
image from an earlier run.

PASS only after the deterministic handler proves the count and order, imports
every source from Codex's generated-images directory into the current run,
opens each raster successfully, verifies approximately 9:16 portrait geometry,
and records a checksum and byte count. Any missing, duplicate, stale, unsafe,
empty, unreadable, non-raster, or wrong-aspect image rejects the full batch.
