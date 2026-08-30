# Image-to-video prompts generated and frozen

Analyze every supplied frozen infographic image internally before writing its
video prompt. Do not expose, summarize, or include the visual analysis in the
response.

The isolated M8M worker must write the minimal draft envelope required by the
draft schema: exactly `count` and `prompts`. The envelope is workflow control
data and is never published. The chosen `video_prompts` output port must be
only the strict JSON array of strings in the original image order. The number
of strings must exactly equal the number of images.

Write every string as a concise forward-time animation direction for one
3-second vertical 9:16 infographic clip. The corresponding supplied image is
the exact target composition and final still, not the opening frame. Describe
one large, immediately readable transformation that occupies a substantial
part of the canvas and resolves precisely into that target. Favor decisive
folding, expanding, sliding, stacking, assembling, locking, or upward motion
over tiny bobs, subtle flexes, micro-rotations, or two-percent camera moves.

Objects may begin beyond the canvas edge when that makes the action stronger.
In particular, when the target contains a human hand placing or holding an
object, the hand must begin fully outside the canvas, travel clearly into the
frame while carrying or guiding that object, place or lock it into its target
position, and finish on the supplied final still. Hold the completed target
composition briefly at the end. Keep the camera locked unless a simple camera
move is essential to the requested transformation.

For later images in a sequence, the opening arrangement may reuse named motifs
from the preceding visual beat, but the prompt must describe those motifs in
words and must never require a second reference image. The one corresponding
supplied image remains the only visual reference and exact final target.

Each prompt should follow this compact pattern:

`In a 3-second vertical 9:16 clip, [large opening arrangement and decisive
object-specific transformation] into the supplied reference image as the exact
final still, [brief final hold and meaning]. Style: Restrained tactile 2D paper
collage stop-motion, crisp machine-cut paper edges, warm cream paper keylines,
halftone photographic textures, soft paper drop shadows, flat Klein Blue color
field throughout. Locked camera and clean visual continuity. No 3D CGI, no
photoreal environments, no text, no letters, no watermark, no UI.`

Vary the opening action and object-specific verbs to match the corresponding
image. Preserve the final composition, subjects, object count, palette,
materials, textures, and background exactly when the action settles. Do not
describe the internal reverse-generation technique; the deterministic Grok
tool handles the 6-second reverse master and converts it to the requested
3-second forward clip.

Do not include headings, numbering, explanations, analysis, notes, Markdown,
properties inside prompt strings, or any additional draft fields. Silently
verify count, order, bold readable motion, exact-final-still grounding,
self-containment, lack of analysis, and strict JSON validity before writing the
draft.
