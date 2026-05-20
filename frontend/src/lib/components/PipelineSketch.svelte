<script lang="ts">
/**
 * Three-stage data-flow diagram of the redaction pipeline. Pure SVG so it
 * scales with the drawer width and stays sharp in dark mode.
 *
 *   image  ─► [ PaddleOCR-VL ]  text + boxes ─► [ GLiNER2 ]  spans ─► pixel boxes
 *              (text detection                  (NER over the
 *               + recognition)                   recognised text)
 */
</script>

<div class="flex flex-col gap-3 rounded-md border border-border bg-background/60 p-3">
  <svg
    viewBox="0 0 360 110"
    class="w-full"
    role="img"
    aria-label="Pipeline data flow"
  >
    <!-- input -->
    <g>
      <text x="6" y="14" class="font-mono fill-text3 text-[9px]">INPUT</text>
      <rect x="0" y="22" width="56" height="46" rx="6" class="fill-card stroke-[var(--border-strong)]" stroke-width="1" />
      <text x="28" y="42" text-anchor="middle" class="text-[10px] font-medium fill-foreground">Image</text>
      <text x="28" y="55" text-anchor="middle" class="font-mono text-[8px] fill-text3">png · pdf</text>
    </g>

    <!-- arrow -->
    <line x1="60" y1="45" x2="86" y2="45" stroke="currentColor" stroke-width="1" class="text-text3" />
    <polygon points="86,42 92,45 86,48" class="fill-text3" />

    <!-- PaddleOCR-VL -->
    <g>
      <text x="98" y="14" class="font-mono fill-text3 text-[9px]">PADDLEOCR-VL</text>
      <rect x="92" y="22" width="116" height="64" rx="6" class="fill-card stroke-primary" stroke-width="1.5" />
      <text x="150" y="40" text-anchor="middle" class="text-[10px] font-medium fill-foreground">Layout + OCR</text>
      <text x="150" y="54" text-anchor="middle" class="font-mono text-[8.5px] fill-text2">text detection</text>
      <text x="150" y="65" text-anchor="middle" class="font-mono text-[8.5px] fill-text2">+ recognition</text>
      <text x="150" y="78" text-anchor="middle" class="font-mono text-[8px] fill-text3">→ lines, boxes, text</text>
    </g>

    <!-- arrow -->
    <line x1="212" y1="45" x2="238" y2="45" stroke="currentColor" stroke-width="1" class="text-text3" />
    <polygon points="238,42 244,45 238,48" class="fill-text3" />

    <!-- GLiNER2 -->
    <g>
      <text x="250" y="14" class="font-mono fill-text3 text-[9px]">GLINER2</text>
      <rect x="244" y="22" width="116" height="64" rx="6" class="fill-card stroke-primary" stroke-width="1.5" />
      <text x="302" y="40" text-anchor="middle" class="text-[10px] font-medium fill-foreground">NER over text</text>
      <text x="302" y="54" text-anchor="middle" class="font-mono text-[8.5px] fill-text2">label-conditioned</text>
      <text x="302" y="65" text-anchor="middle" class="font-mono text-[8.5px] fill-text2">PII extraction</text>
      <text x="302" y="78" text-anchor="middle" class="font-mono text-[8px] fill-text3">→ char spans</text>
    </g>

    <!-- output band -->
    <g>
      <text x="6" y="100" class="font-mono fill-text3 text-[9px]">FRONTEND</text>
      <text x="60" y="100" class="font-mono fill-text2 text-[9.5px]">
        char spans + OCR geometry → pixel boxes drawn on the canvas
      </text>
    </g>
  </svg>

  <p class="text-[10.5px] leading-relaxed text-muted-foreground">
    PaddleOCR-VL handles <span class="text-foreground">text detection</span> and
    <span class="text-foreground">recognition</span>. GLiNER2 runs over the
    recognised text and labels every PII span. The frontend then projects each
    char-span back onto the OCR line geometry to render a redaction box.
  </p>
</div>
