type ExtractVariables<T extends string> =
  T extends `${string}{${infer Param}}${infer Rest}`
    ? Param | ExtractVariables<Rest>
    : never;

type InferVariables<T extends string> = {
  [K in ExtractVariables<T>]: string;
};

class PromptTemplate<T extends string> {
  constructor(private template: T) {}

  compile(variables: InferVariables<T>): string {
    let result = this.template as string;
    (Object.entries(variables) as [ExtractVariables<T>, string][]).forEach(
      ([key, value]) => {
        result = result.replace(new RegExp(`\\{${key}\\}`, "g"), value);
      }
    );
    return result;
  }
}

const createPrompt = <T extends string>(template: T) => {
  return new PromptTemplate(template);
};

const prompts = {
  optimizeImage:
    createPrompt(`Optimize and enhance the prompts provided for image generation to ensure that Midjourney or other diffusion models can generate excellent views.

-You should provide a detailed and accurate description of the prompt view. If the provided prompt is too simple, you should add some additional details to enrich it and improve the expression of the image content. If necessary, you can use some famous IP names.
-Introduce the topic with higher weights. Avoid using introductory phrases such as' this image displays' or 'on-site'. Avoid using terms that describe cultural values or spirits, such as "creating an xxx atmosphere" or "enhancing the xxx scene".
-Avoid ambiguous expressions and focus only on describing the scene you see in clear and specific terms. Avoid over interpreting abstract or indescribable elements.
-When there are spelling or grammar errors in the input content, you should correct them to improve the accuracy of the prompts.
-Translate input content into accurate and natural sounding English, regardless of the original language.

Input content:<text>
{input}
</text>

Always return results in plain text format and do not add any other content.`),

  optimizeVideo:
    createPrompt(`Optimize and enhance the prompts provided for video generation to ensure that AI video models can generate excellent results.

- You should provide a detailed and accurate description of the scene, action, and movement for the video. If the provided prompt is too simple, add additional details to enrich it and improve the expression of the video content.
- Focus on describing dynamic elements, motion, and temporal changes that would be appropriate for video rather than static images.
- Introduce the main subject and action with higher weights. Avoid using introductory phrases such as 'this video shows' or 'in this scene'.
- CRITICAL: Preserve and enforce all explicit negative constraints and technical directives from the original prompt. If the user specifies:
  - "no camera movement" / "locked-off" / "static camera" / "no pan/tilt/zoom" → Do NOT add any camera movement, pan, tilt, zoom, dolly, or crane. Explicitly state "locked-off static camera, zero movement".
  - "no fade to black" / "no fade" / "no transition" / "end cleanly" → Do NOT add fade-out, fade to black, dissolve, or transition. Explicitly state "clean hard cut ending, no fade".
  - "no added text" / "no text" / "no titles" / "no overlay" → Explicitly state "no text overlay, no titles, no watermark".
  - "stable final frame" / "hold frame" / "freeze" / "perfectly stable" → Preserve the hold duration (e.g., "hold perfectly stable final frame for 1 second"), emphasize bit-identical frames, no drift, no flicker.
  - "minimal breathing" / "only breathing" / "subtle motion" → Limit subject motion to ultra-minimal natural breathing only (chest rise/fall ~1-2px, no limb or head movement), background fully locked.
  Never override these constraints with generic enhancement. Reinforce them verbatim in the optimized output.
- Be specific about camera movements, transitions, and timing ONLY if the original prompt does not forbid them. If camera work is allowed, describe it precisely (e.g., "camera slowly panning across the landscape"). If forbidden, explicitly reaffirm the locked-off state.
- For prompts requiring a stable hold/freeze at the end: always specify duration, stability ("perfectly stable, bit-identical frames, zero drift"), and clean ending ("hard cut, no fade, no black tail").
- Avoid ambiguous expressions and focus only on describing the scene in clear and specific terms.
- When there are spelling or grammar errors in the input content, correct them to improve the accuracy of the prompts.
- Translate input content into accurate and natural sounding English, regardless of the original language.

Input content:<text>
{input}
</text>

Always return results in plain text format and do not add any other content.`),

  // 示例：多变量模板
  customPrompt: createPrompt(
    `Create a {style} image of {subject} with {mood} mood, using {technique} technique.`
  ),
} as const;

export type Prompts = typeof prompts;
export default prompts;
