/**
 * Valibot schema mirroring {@link PipelineConfig}. Used to validate the blob
 * we hydrate from localStorage and any future server-side wire payload.
 *
 * Why valibot (not zod): same DSL surface, ~5× smaller in the client bundle.
 * If we ever need shared backend Python validation we'll port to pydantic /
 * msgspec on that side — schema-first wins either way.
 */
import * as v from 'valibot';

const RegexModeSchema = v.picklist(['full', 'partial', 'exclude']);

const LabelRuleSchema = v.object({
  regex: v.string(),
  regexMode: RegexModeSchema,
  threshold: v.pipe(v.number(), v.minValue(0), v.maxValue(1)),
  validateLuhn: v.boolean(),
});

const CustomLabelSchema = v.object({
  displayLabel: v.pipe(v.string(), v.minLength(1)),
  // Accept #rgb / #rrggbb (case-insensitive). Anything else falls back at load.
  color: v.pipe(v.string(), v.regex(/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/)),
  description: v.string(),
});

const PaddleConfigSchema = v.object({
  layoutThreshold: v.pipe(v.number(), v.minValue(0), v.maxValue(1)),
  useDocOrientationClassify: v.boolean(),
  useDocUnwarping: v.boolean(),
  useTextlineOrientation: v.boolean(),
  useChartRecognition: v.boolean(),
  useSealRecognition: v.boolean(),
  useOcrForImageBlock: v.boolean(),
});

const VlmConfigSchema = v.object({
  temperature: v.pipe(v.number(), v.minValue(0), v.maxValue(2)),
  topP: v.pipe(v.number(), v.minValue(0), v.maxValue(1)),
  repetitionPenalty: v.pipe(v.number(), v.minValue(0.5), v.maxValue(3)),
  maxNewTokens: v.pipe(v.number(), v.minValue(32), v.maxValue(32768)),
  minPixels: v.pipe(v.number(), v.minValue(0)),
  maxPixels: v.pipe(v.number(), v.minValue(0)),
});

const GlinerConfigSchema = v.object({
  modelName: v.pipe(v.string(), v.minLength(1)),
  threshold: v.pipe(v.number(), v.minValue(0), v.maxValue(1)),
  enabledLabels: v.array(v.string()),
  descriptions: v.record(v.string(), v.string()),
  rules: v.record(v.string(), LabelRuleSchema),
  customLabels: v.record(v.string(), CustomLabelSchema),
});

export const PipelineConfigSchema = v.object({
  paddleocr: PaddleConfigSchema,
  vlm: VlmConfigSchema,
  gliner: GlinerConfigSchema,
});

export type PipelineConfigParsed = v.InferOutput<typeof PipelineConfigSchema>;

/** Validate a custom-label key — produced by the user's "Add custom label" form. */
export const CustomLabelKeySchema = v.pipe(
  v.string(),
  v.minLength(1, 'Key cannot be empty'),
  v.regex(/^[a-z][a-z0-9_]*$/, 'Lowercase letters / digits / underscore, must start with a letter'),
  v.maxLength(48, 'Key is too long'),
);

/** Partial-validation helper: returns `null` when parse succeeds, or a
 *  one-line human message when it fails. Used by the localStorage loader. */
export function tryValidate(raw: unknown): { ok: true } | { ok: false; reason: string } {
  const r = v.safeParse(PipelineConfigSchema, raw);
  if (r.success) return { ok: true };
  const first = r.issues?.[0];
  const path = first?.path?.map((p) => String(p.key)).join('.') ?? '';
  return { ok: false, reason: path ? `${path}: ${first?.message}` : (first?.message ?? 'invalid') };
}
