/**
 * Editor state — Svelte 5 runes, module-scoped singleton.
 *
 * Multi-page model:
 *   - `pages[]` holds one analysed Page per uploaded image (PDFs are
 *     rasterised first; see ../lib/pdf.ts).
 *   - The "active" working fields (img/width/height/boxes/spans/…) are a
 *     live working copy of pages[activeIdx]. Mutations (moveBox, …) edit
 *     this copy directly; `goTo()` snapshots it back into pages on
 *     navigation so edits persist when paginating.
 *   - `engine.analyze()` does the inference; this file is engine-agnostic.
 */
import { SvelteSet } from 'svelte/reactivity';
import { engine } from './engine';
import { isPdf, pdfToImageFiles } from './pdf';
import { tryValidate } from './pipelineConfig.schema';
import {
  type AnonymizeResult,
  type CatMeta,
  DEFAULT_PIPELINE_CONFIG,
  type DragState,
  type EditorBox,
  type Mode,
  type OcrLine,
  type PiiSpan,
  type PipelineConfig,
} from './types';

type Page = {
  filename: string;
  width: number;
  height: number;
  img: HTMLImageElement;
  objectUrl: string;
  sourceText: string;
  spans: PiiSpan[];
  boxes: EditorBox[];
  ocrLines: OcrLine[];
  /** Original (or PDF-rasterised) file kept so Run can re-analyse without a re-upload. */
  file: File;
};

const PIPELINE_CONFIG_KEY = 'ranymizer:pipeline-config';

function loadPipelineConfig(): PipelineConfig {
  if (typeof localStorage === 'undefined') return structuredClone(DEFAULT_PIPELINE_CONFIG);
  try {
    const raw = localStorage.getItem(PIPELINE_CONFIG_KEY);
    if (!raw) return structuredClone(DEFAULT_PIPELINE_CONFIG);

    const parsed = JSON.parse(raw) as Partial<PipelineConfig>;

    // Deep-merge first so an older saved blob with missing sections still
    // loads with new defaults filling the gaps.
    const merged: PipelineConfig = {
      paddleocr: { ...DEFAULT_PIPELINE_CONFIG.paddleocr, ...(parsed.paddleocr ?? {}) },
      vlm: { ...DEFAULT_PIPELINE_CONFIG.vlm, ...(parsed.vlm ?? {}) },
      gliner: {
        ...DEFAULT_PIPELINE_CONFIG.gliner,
        ...(parsed.gliner ?? {}),
        descriptions: {
          ...DEFAULT_PIPELINE_CONFIG.gliner.descriptions,
          ...(parsed.gliner?.descriptions ?? {}),
        },
        rules: {
          ...DEFAULT_PIPELINE_CONFIG.gliner.rules,
          ...(parsed.gliner?.rules ?? {}),
        },
        customLabels: {
          ...DEFAULT_PIPELINE_CONFIG.gliner.customLabels,
          ...(parsed.gliner?.customLabels ?? {}),
        },
      },
    };

    // Validate against the valibot schema — if a saved field is the wrong
    // type (corrupted blob, manual edit, post-migration shape change) we
    // discard the whole thing instead of letting bad data crash the UI.
    const check = tryValidate(merged);
    if (!check.ok) {
      console.warn('[ranymizer] discarding invalid pipeline config:', check.reason);
      return structuredClone(DEFAULT_PIPELINE_CONFIG);
    }
    return merged;
  } catch {
    return structuredClone(DEFAULT_PIPELINE_CONFIG);
  }
}

export class EditorState {
  // ── lifecycle ─────────────────────────────────────────────────────
  loading = $state(false);
  loadingMessage = $state(''); // local-engine status / model-download text
  loadingProgress = $state<{ done: number; total: number } | null>(null);
  error = $state<string | null>(null);

  /** Current stage of the streaming backend pipeline. Drives the per-node
   *  status dots in PipelineSketch and the stage-aware label in the canvas
   *  overlay. `idle` whenever nothing is running. */
  pipelineStage = $state<'idle' | 'ocr' | 'gliner' | 'done'>('idle');

  // ── pipeline config (persisted) ───────────────────────────────────
  pipelineConfig = $state<PipelineConfig>(loadPipelineConfig());
  settingsOpen = $state(false);

  // ── live working copy of the active page ──────────────────────────
  img = $state<HTMLImageElement | null>(null);
  width = $state(0);
  height = $state(0);
  filename = $state('');
  sourceText = $state('');
  spans = $state<PiiSpan[]>([]);
  boxes = $state<EditorBox[]>([]);
  ocrLines = $state<OcrLine[]>([]);
  showOcrLines = $state(false);
  // Preview-only: paint boxes translucently so users can see *why* each
  // region was redacted. Never applied to the export canvas (the PNG always
  // uses solid `maskColor`).
  //   showCategoryColors = on  → paint preview at maskAlpha
  //   colorMaskMode = 'unified'      → all boxes in maskColor
  //   colorMaskMode = 'per-category' → each box in its category colour
  showCategoryColors = $state(false);
  /**
   * 'unified'      → all visible boxes painted in maskColor at maskAlpha
   * 'per-category' → each box in its category colour at maskAlpha
   * 'hide'         → don't paint any masks (preview only — export PNG is
   *                  unaffected and still uses maskColor)
   */
  colorMaskMode = $state<'unified' | 'per-category' | 'hide'>('unified');
  maskAlpha = $state(0.6);
  // Solid mask color used in the unified preview and always for the export PNG.
  maskColor = $state('#000000');
  // Default category for the next drawn box.
  drawLabel = $state('custom');
  // Thumbnail carousel visibility — only matters when there are >1 pages.
  showThumbnails = $state(true);
  /** Raw category meta as returned by the backend (color + display label per
   *  default PII key). User-defined `customLabels` are merged in via the
   *  `catMeta` derived below. */
  rawCatMeta = $state<Record<string, CatMeta>>({});

  /** Effective category meta seen by every consumer: backend defaults merged
   *  with user-defined custom labels from pipelineConfig. */
  catMeta = $derived.by<Record<string, CatMeta>>(() => {
    const out: Record<string, CatMeta> = { ...this.rawCatMeta };
    for (const [key, c] of Object.entries(this.pipelineConfig.gliner.customLabels)) {
      out[key] = { color: c.color, label: c.displayLabel };
    }
    return out;
  });

  activeCats = new SvelteSet<string>();

  // ── editor tool state ─────────────────────────────────────────────
  mode = $state<Mode>('select');
  scale = $state(1);
  /** Primary selection — used by the canvas drag/move target and as the
   *  anchor for shift-range selection in the sidebar. */
  selected = $state<number | null>(null);
  /** Set of all selected box ids. When size > 1 the sidebar enters bulk
   *  mode. `selected` is always either null or a member of this set. */
  selectedIds = new SvelteSet<number>();
  drag = $state<DragState | null>(null);
  cursor = $state<{ x: number; y: number } | null>(null);

  // ── multi-page ────────────────────────────────────────────────────
  pages = $state<Page[]>([]);
  activeIdx = $state(0);

  // ── non-reactive bookkeeping ──────────────────────────────────────
  #nextId = 1;
  #uploadId = 0;
  #objectUrls: string[] = [];

  // ── undo / redo (per-page box history) ────────────────────────────
  // Stack of `boxes[]` snapshots keyed by activeIdx. Each box mutation
  // pushes the *previous* state onto undo; redo is populated when we pop.
  // Capped to UNDO_LIMIT entries per page so memory stays bounded.
  #undoStacks = new Map<number, EditorBox[][]>();
  #redoStacks = new Map<number, EditorBox[][]>();
  static readonly #UNDO_LIMIT = 100;
  canUndo = $state(false);
  canRedo = $state(false);

  #refreshUndoFlags(): void {
    this.canUndo = (this.#undoStacks.get(this.activeIdx)?.length ?? 0) > 0;
    this.canRedo = (this.#redoStacks.get(this.activeIdx)?.length ?? 0) > 0;
  }

  /**
   * Take a snapshot of the current page's boxes before a mutation.
   * Pushes onto undo, clears redo (new edit invalidates the redo branch).
   * Boxes are deep-cloned so later in-place edits don't leak into history.
   */
  #snapshotForUndo(): void {
    const snapshot = this.boxes.map((b) => ({ ...b }));
    const stack = this.#undoStacks.get(this.activeIdx) ?? [];
    stack.push(snapshot);
    if (stack.length > EditorState.#UNDO_LIMIT) stack.shift();
    this.#undoStacks.set(this.activeIdx, stack);
    this.#redoStacks.delete(this.activeIdx);
    this.#refreshUndoFlags();
  }

  undo(): void {
    const stack = this.#undoStacks.get(this.activeIdx);
    if (!stack || stack.length === 0) return;
    const previous = stack.pop();
    if (!previous) return;
    const redoStack = this.#redoStacks.get(this.activeIdx) ?? [];
    redoStack.push(this.boxes.map((b) => ({ ...b })));
    this.#redoStacks.set(this.activeIdx, redoStack);
    this.boxes = previous;
    this.selected = null;
    this.#refreshUndoFlags();
  }

  redo(): void {
    const stack = this.#redoStacks.get(this.activeIdx);
    if (!stack || stack.length === 0) return;
    const next = stack.pop();
    if (!next) return;
    const undoStack = this.#undoStacks.get(this.activeIdx) ?? [];
    undoStack.push(this.boxes.map((b) => ({ ...b })));
    this.#undoStacks.set(this.activeIdx, undoStack);
    this.boxes = next;
    this.selected = null;
    this.#refreshUndoFlags();
  }

  // ── derived ───────────────────────────────────────────────────────
  catCounts = $derived.by(() => {
    const counts: Record<string, number> = {};
    for (const b of this.boxes) {
      if (b.custom) continue;
      counts[b.label] = (counts[b.label] ?? 0) + 1;
    }
    return counts;
  });

  visibleBoxes = $derived(this.boxes.filter((b) => this.isVisible(b)));

  /** Ids of boxes whose rectangle intersects at least one other *visible* box. */
  overlappingIds = $derived.by(() => {
    const out = new Set<number>();
    const vis = this.visibleBoxes;
    for (let i = 0; i < vis.length; i++) {
      const a = vis[i];
      for (let j = i + 1; j < vis.length; j++) {
        const b = vis[j];
        if (a.x + a.w <= b.x || b.x + b.w <= a.x) continue;
        if (a.y + a.h <= b.y || b.y + b.h <= a.y) continue;
        out.add(a.id);
        out.add(b.id);
      }
    }
    return out;
  });

  /** "label::text" → list of box ids that share that combo (≥ 2 members). */
  duplicateGroups = $derived.by(() => {
    const groups = new Map<string, number[]>();
    for (const b of this.boxes) {
      const t = (b.text || '').trim().toLowerCase();
      if (!t) continue;
      const key = `${b.label}::${t}`;
      const list = groups.get(key);
      if (list) list.push(b.id);
      else groups.set(key, [b.id]);
    }
    for (const [k, ids] of groups) if (ids.length < 2) groups.delete(k);
    return groups;
  });

  /** Flat set of ids that appear in any duplicate group. */
  duplicateIds = $derived.by(() => {
    const out = new Set<number>();
    for (const ids of this.duplicateGroups.values()) for (const id of ids) out.add(id);
    return out;
  });

  selectedBox = $derived(
    this.selected === null ? null : (this.boxes.find((b) => b.id === this.selected) ?? null),
  );

  pageCount = $derived(this.pages.length);
  hasMultiple = $derived(this.pages.length > 1);
  hasImage = $derived(this.pages.length > 0);

  /**
   * Every box across every page, paired with the page it lives on.
   * The active page's boxes come from the live working copy (`this.boxes`)
   * so in-flight edits show up immediately; other pages read their
   * snapshot in `pages[i].boxes`.
   */
  allBoxes = $derived.by<Array<{ pageIdx: number; box: EditorBox }>>(() => {
    const out: Array<{ pageIdx: number; box: EditorBox }> = [];
    for (let i = 0; i < this.pages.length; i++) {
      const source = i === this.activeIdx ? this.boxes : this.pages[i].boxes;
      for (const box of source) out.push({ pageIdx: i, box });
    }
    return out;
  });

  spansForPage(pageIdx: number): PiiSpan[] {
    if (pageIdx === this.activeIdx) return this.spans;
    return this.pages[pageIdx]?.spans ?? [];
  }

  // ── helpers ───────────────────────────────────────────────────────
  isVisible(b: EditorBox): boolean {
    if (!b.enabled) return false;
    if (!b.custom && !this.activeCats.has(b.label)) return false;
    return true;
  }

  #revokeAllObjectUrls() {
    for (const u of this.#objectUrls) URL.revokeObjectURL(u);
    this.#objectUrls = [];
  }

  #loadImage(src: string): Promise<HTMLImageElement> {
    return new Promise((res, rej) => {
      const img = new Image();
      img.onload = () => res(img);
      img.onerror = () => rej(new Error('image load failed'));
      img.src = src;
    });
  }

  // ── upload ────────────────────────────────────────────────────────
  /** Backward-compat shortcut for the single-file path (paste, etc.). */
  upload(file: File): Promise<void> {
    return this.uploadFiles([file]);
  }

  /**
   * Accepts any mix of images + PDFs. PDFs are rasterised page-by-page;
   * every effective image is analysed sequentially and pushed to `pages`.
   *
   * Pass `{ append: true }` to keep existing pages and tack the new ones
   * onto the end — used by the "New image" / "Add image" path so users can
   * keep navigating between their accumulated uploads.
   */
  async uploadFiles(files: File[], opts: { append?: boolean } = {}): Promise<void> {
    const myId = ++this.#uploadId;

    this.loading = true;
    this.loadingMessage = '';
    this.loadingProgress = null;
    this.error = null;
    if (opts.append) {
      // Snapshot the current working page so its in-flight edits aren't lost
      // when we navigate away to the first new page after analysis.
      this.#saveActivePage();
    } else {
      this.#revokeAllObjectUrls();
      this.pages = [];
      this.activeIdx = 0;
      this.activeCats.clear();
    }

    // Expand PDFs to per-page image Files.
    const expanded: File[] = [];
    for (const f of files) {
      if (isPdf(f)) {
        this.loadingMessage = `Rasterising ${f.name}…`;
        try {
          const imgs = await pdfToImageFiles(f);
          expanded.push(...imgs);
        } catch (e) {
          console.error('pdf rasterise failed:', e);
        }
      } else {
        expanded.push(f);
      }
      if (myId !== this.#uploadId) return;
    }

    if (expanded.length === 0) {
      this.error = 'no usable images';
      this.loading = false;
      this.loadingMessage = '';
      return;
    }

    // Hydrate catMeta on first upload so the sidebar/settings drawer can
    // render category colours even before the user presses Run.
    const catMetaPromise = engine.meta().catch(() => ({}) as Record<string, CatMeta>);
    const firstNewIdx = this.pages.length;

    for (let i = 0; i < expanded.length; i++) {
      if (myId !== this.#uploadId) return;
      const file = expanded[i];
      this.loadingProgress = { done: i, total: expanded.length };
      this.loadingMessage = `Loading ${i + 1}/${expanded.length}: ${file.name}`;

      const objectUrl = URL.createObjectURL(file);
      this.#objectUrls.push(objectUrl);

      try {
        const img = await this.#loadImage(objectUrl);
        if (myId !== this.#uploadId) return;

        // Skeleton page — no spans/boxes/ocrLines until the user presses Run.
        const page: Page = {
          filename: file.name,
          width: img.naturalWidth,
          height: img.naturalHeight,
          img,
          objectUrl,
          sourceText: '',
          spans: [],
          boxes: [],
          ocrLines: [],
          file,
        };
        this.pages = [...this.pages, page];

        if (this.pages.length === firstNewIdx + 1) {
          if (Object.keys(this.rawCatMeta).length === 0) {
            this.rawCatMeta = await catMetaPromise;
          }
          this.activeIdx = firstNewIdx;
          this.#loadActivePage();
        }
      } catch (e) {
        if (myId !== this.#uploadId) return;
        const msg = e instanceof Error ? e.message : String(e);
        console.error('load failed for', file.name, '—', msg);
      }
    }

    if (myId !== this.#uploadId) return;
    this.loadingProgress = null;
    this.loading = false;
    this.loadingMessage = '';
    if (this.pages.length === 0) this.error = 'no usable images';
  }

  #resultToPage(r: AnonymizeResult, img: HTMLImageElement, objectUrl: string, file: File): Page {
    return {
      filename: r.filename,
      width: r.width,
      height: r.height,
      img,
      objectUrl,
      sourceText: r.text ?? '',
      spans: r.spans ?? [],
      boxes: (r.boxes ?? []).map((b) => ({
        ...b,
        id: this.#nextId++,
        enabled: true,
        custom: false,
      })),
      ocrLines: r.ocr_lines ?? [],
      file,
    };
  }

  /**
   * Re-run the pipeline on every uploaded page with the current pipelineConfig.
   * Custom user-drawn boxes are preserved; PII-derived boxes are replaced with
   * the fresh result. Triggered by the navbar Run button after settings change.
   */
  async run(): Promise<void> {
    if (this.pages.length === 0 || this.loading) return;
    const myId = ++this.#uploadId;
    this.loading = true;
    this.loadingMessage = 'Running pipeline…';
    this.loadingProgress = { done: 0, total: this.pages.length };
    this.pipelineStage = 'idle';
    this.error = null;

    const refreshed: Page[] = [];
    for (let i = 0; i < this.pages.length; i++) {
      if (myId !== this.#uploadId) return;
      const existing = this.pages[i];
      const customBoxes = existing.boxes.filter((b) => b.custom);
      this.loadingProgress = { done: i, total: this.pages.length };
      this.loadingMessage =
        this.pages.length > 1
          ? `Running ${i + 1}/${this.pages.length}: ${existing.filename}`
          : `Running: ${existing.filename}`;

      try {
        const result = await engine.analyze(existing.file, {
          config: this.pipelineConfig,
          // Per-stage SSE frames from the backend generator. Paint OCR
          // results (text + word boxes) the moment PaddleOCR finishes so
          // the text sidebar populates ~1s earlier than the legacy single
          // response, and flip the pipeline-graph indicators between stages.
          onStage: (event) => {
            if (myId !== this.#uploadId) return;
            if (event.stage === 'ocr_started') {
              this.pipelineStage = 'ocr';
            } else if (event.stage === 'ocr_done') {
              // Push OCR text + word boxes onto the live page immediately.
              // Spans/boxes stay empty until `done`.
              if (i === this.activeIdx) {
                this.sourceText = event.text ?? '';
                this.ocrLines = event.ocr_lines ?? [];
                this.width = event.width;
                this.height = event.height;
              }
            } else if (event.stage === 'gliner_started') {
              this.pipelineStage = 'gliner';
            } else if (event.stage === 'done') {
              this.pipelineStage = 'done';
            }
          },
        });
        if (myId !== this.#uploadId) return;
        if (result.error) {
          console.error('re-run failed for', existing.filename, '—', result.error);
          refreshed.push(existing);
          continue;
        }
        const updated = this.#resultToPage(result, existing.img, existing.objectUrl, existing.file);
        updated.boxes = [...updated.boxes, ...customBoxes];
        refreshed.push(updated);
      } catch (e) {
        if (myId !== this.#uploadId) return;
        console.error('re-run failed for', existing.filename, '—', e);
        refreshed.push(existing);
      }
    }

    if (myId !== this.#uploadId) return;
    this.pages = refreshed;
    this.activeCats.clear();
    for (const page of refreshed) {
      for (const b of page.boxes) if (!b.custom) this.activeCats.add(b.label);
    }
    this.#loadActivePage();
    this.loading = false;
    this.loadingProgress = null;
    this.loadingMessage = '';
    this.pipelineStage = 'idle';
  }

  /** Persist the current pipelineConfig to localStorage. Call after edits. */
  persistPipelineConfig(): void {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(PIPELINE_CONFIG_KEY, JSON.stringify(this.pipelineConfig));
    } catch {
      // quota exceeded / private mode — ignore, persistence is best-effort
    }
  }

  resetPipelineConfig(): void {
    this.pipelineConfig = structuredClone(DEFAULT_PIPELINE_CONFIG);
    this.persistPipelineConfig();
  }

  // ── pagination ────────────────────────────────────────────────────
  /** Snapshot the live working copy back into pages[activeIdx]. */
  #saveActivePage() {
    const p = this.pages[this.activeIdx];
    if (!p) return;
    p.boxes = this.boxes;
    p.spans = this.spans;
    p.sourceText = this.sourceText;
    p.ocrLines = this.ocrLines;
  }

  /** Load pages[activeIdx] into the live working copy. */
  #loadActivePage() {
    const p = this.pages[this.activeIdx];
    if (!p) {
      this.img = null;
      this.width = this.height = 0;
      this.filename = '';
      this.sourceText = '';
      this.spans = [];
      this.boxes = [];
      this.ocrLines = [];
      return;
    }
    this.img = p.img;
    this.width = p.width;
    this.height = p.height;
    this.filename = p.filename;
    this.sourceText = p.sourceText;
    this.spans = p.spans;
    this.boxes = p.boxes;
    this.ocrLines = p.ocrLines;
    this.selectedIds.clear();
    this.selected = null;
    this.drag = null;
  }

  goTo(idx: number) {
    if (idx < 0 || idx >= this.pages.length || idx === this.activeIdx) return;
    this.#saveActivePage();
    this.activeIdx = idx;
    this.#loadActivePage();
    this.#refreshUndoFlags();
  }

  prev() {
    this.goTo(this.activeIdx - 1);
  }
  next() {
    this.goTo(this.activeIdx + 1);
  }

  /** Cancel an in-flight upload or pipeline run. Bumps `#uploadId` so the
   *  loop's `myId !== this.#uploadId` check breaks out on the next yielded
   *  SSE frame; any later frames from the still-running backend are
   *  silently dropped. Resets the UI to idle. */
  cancel(): void {
    if (!this.loading) return;
    this.#uploadId++;
    this.loading = false;
    this.loadingProgress = null;
    this.loadingMessage = '';
    this.pipelineStage = 'idle';
  }

  reset() {
    this.#uploadId++;
    this.#revokeAllObjectUrls();

    this.pages = [];
    this.activeIdx = 0;
    this.error = null;
    this.loadingMessage = '';
    this.loadingProgress = null;
    this.img = null;
    this.boxes = [];
    this.spans = [];
    this.ocrLines = [];
    this.sourceText = '';
    this.filename = '';
    this.width = 0;
    this.height = 0;
    this.selected = null;
    this.drag = null;
    this.activeCats.clear();
    this.mode = 'select';
    this.scale = 1;
    // catMeta is static; keep it cached.
  }

  // ── mutations ─────────────────────────────────────────────────────
  toggleCategory(cat: string) {
    if (this.activeCats.has(cat)) this.activeCats.delete(cat);
    else this.activeCats.add(cat);
  }

  setMode(m: Mode) {
    this.mode = m;
  }

  removeSelected() {
    if (this.selected === null) return;
    this.#snapshotForUndo();
    this.boxes = this.boxes.filter((b) => b.id !== this.selected);
    this.selectedIds.delete(this.selected);
    this.selected = null;
  }

  // ── multi-selection ───────────────────────────────────────────────
  /** Replace the selection set with just `id` and set it as the anchor. */
  selectOnly(id: number): void {
    this.selectedIds.clear();
    this.selectedIds.add(id);
    this.selected = id;
  }

  /**
   * Sidebar uses this when a row's box lives on a different page —
   * navigate there first, then make it the single selection.
   */
  selectAndNavigate(pageIdx: number, id: number): void {
    if (pageIdx !== this.activeIdx) this.goTo(pageIdx);
    this.selectOnly(id);
  }

  /** Find which page index a globally-unique box id lives on, or -1. */
  pageOfBox(id: number): number {
    for (let i = 0; i < this.pages.length; i++) {
      const source = i === this.activeIdx ? this.boxes : this.pages[i].boxes;
      if (source.some((b) => b.id === id)) return i;
    }
    return -1;
  }

  /** Cmd/Ctrl-click — toggle membership without clearing the rest. */
  selectToggle(id: number): void {
    if (this.selectedIds.has(id)) {
      this.selectedIds.delete(id);
      if (this.selected === id) {
        const first = this.selectedIds.values().next().value;
        this.selected = first ?? null;
      }
    } else {
      this.selectedIds.add(id);
      this.selected = id;
    }
  }

  /**
   * Shift-click — select every id between the current anchor (`selected`)
   * and `id` in `idsInOrder` (the visible order in the sidebar). If there
   * is no anchor, behaves like `selectOnly`.
   */
  selectRange(id: number, idsInOrder: number[]): void {
    if (this.selected === null) {
      this.selectOnly(id);
      return;
    }
    const anchor = idsInOrder.indexOf(this.selected);
    const target = idsInOrder.indexOf(id);
    if (anchor < 0 || target < 0) {
      this.selectOnly(id);
      return;
    }
    const [lo, hi] = anchor <= target ? [anchor, target] : [target, anchor];
    this.selectedIds.clear();
    for (let i = lo; i <= hi; i++) this.selectedIds.add(idsInOrder[i]);
    this.selected = id;
  }

  selectAll(ids: number[]): void {
    this.selectedIds.clear();
    for (const id of ids) this.selectedIds.add(id);
    this.selected = ids.length > 0 ? ids[ids.length - 1] : null;
  }

  clearSelection(): void {
    this.selectedIds.clear();
    this.selected = null;
  }

  /**
   * Delete every box in `selectedIds` across all pages in one undo step
   * for the active page. (Edits on other pages don't go through the undo
   * stack right now — that's a known limit; see canUndo docs.)
   */
  removeSelectedMany(): void {
    if (this.selectedIds.size === 0) return;
    this.#snapshotForUndo();
    this.#saveActivePage();
    const ids = this.selectedIds;
    for (let i = 0; i < this.pages.length; i++) {
      this.pages[i].boxes = this.pages[i].boxes.filter((b) => !ids.has(b.id));
    }
    this.#loadActivePage();
    this.selectedIds.clear();
    this.selected = null;
  }

  /** Set the same label on every box in `selectedIds` across all pages. */
  setBoxLabelMany(label: string): void {
    if (this.selectedIds.size === 0) return;
    this.#snapshotForUndo();
    this.#saveActivePage();
    const ids = this.selectedIds;
    let changedAny = false;
    for (let i = 0; i < this.pages.length; i++) {
      for (const b of this.pages[i].boxes) {
        if (!ids.has(b.id) || b.label === label) continue;
        b.label = label;
        changedAny = true;
      }
    }
    this.#loadActivePage();
    if (label !== 'custom' && changedAny) this.activeCats.add(label);
  }

  /** Collect text from every OCR line that overlaps the given rectangle.
   *  An overlap counts if either line center is inside the box OR ≥ 30% of
   *  the line's area falls inside it. Lines are joined with spaces. */
  textInBox(x: number, y: number, w: number, h: number): string {
    const bx1 = x;
    const by1 = y;
    const bx2 = x + w;
    const by2 = y + h;
    const out: string[] = [];
    for (const ln of this.ocrLines) {
      const lx1 = ln.x;
      const ly1 = ln.y;
      const lx2 = ln.x + ln.w;
      const ly2 = ln.y + ln.h;
      const ix = Math.max(0, Math.min(bx2, lx2) - Math.max(bx1, lx1));
      const iy = Math.max(0, Math.min(by2, ly2) - Math.max(by1, ly1));
      const inter = ix * iy;
      if (inter === 0) continue;
      const cx = (lx1 + lx2) / 2;
      const cy = (ly1 + ly2) / 2;
      const centerInside = cx >= bx1 && cx <= bx2 && cy >= by1 && cy <= by2;
      const ratio = inter / Math.max(1, (lx2 - lx1) * (ly2 - ly1));
      if (centerInside || ratio >= 0.3) out.push(ln.text);
    }
    return out.join(' ');
  }

  addCustomBox(x: number, y: number, w: number, h: number) {
    this.#snapshotForUndo();
    const label = this.drawLabel || 'custom';
    const nb: EditorBox = {
      id: this.#nextId++,
      x: Math.round(x),
      y: Math.round(y),
      w: Math.round(w),
      h: Math.round(h),
      label,
      // Pull whatever OCR text falls under the rectangle the user just drew,
      // so the row in the side panel actually says what was redacted.
      text: this.textInBox(x, y, w, h),
      enabled: true,
      // User-drawn boxes are always `custom: true` — the label is only metadata.
      // Without this, picking a real category would hide the box behind the
      // category filter (see isVisible).
      custom: true,
    };
    this.boxes = [...this.boxes, nb];
    this.selected = nb.id;
    // Keep the filter in sync so the new box is visible immediately.
    if (label !== 'custom') this.activeCats.add(label);
  }

  /** Manually override the captured text on a box (used by the inline editor). */
  setBoxText(id: number, text: string) {
    const b = this.boxes.find((b) => b.id === id);
    if (!b || b.text === text) return;
    this.#snapshotForUndo();
    b.text = text;
  }

  /** Reassign a box's category. Preserves the `custom` flag so visibility
   *  doesn't flip based on the category filter. */
  setBoxLabel(id: number, label: string) {
    const b = this.boxes.find((b) => b.id === id);
    if (!b || b.label === label) return;
    this.#snapshotForUndo();
    b.label = label;
    if (label !== 'custom') this.activeCats.add(label);
  }

  /** Toggle a box's enabled flag (the "include/exclude" checkbox). */
  setBoxEnabled(id: number, enabled: boolean) {
    const b = this.boxes.find((b) => b.id === id);
    if (!b || b.enabled === enabled) return;
    this.#snapshotForUndo();
    b.enabled = enabled;
  }

  removeBox(id: number) {
    if (!this.boxes.some((b) => b.id === id)) return;
    this.#snapshotForUndo();
    this.boxes = this.boxes.filter((b) => b.id !== id);
    if (this.selected === id) this.selected = null;
  }

  /**
   * Mark the start of an interactive move so a drag captures a single undo
   * entry (called once on mousedown), instead of one per cursor frame.
   */
  beginMove(): void {
    this.#snapshotForUndo();
  }

  moveBox(id: number, x: number, y: number) {
    const b = this.boxes.find((b) => b.id === id);
    if (!b) return;
    b.x = Math.max(0, Math.min(this.width - b.w, Math.round(x)));
    b.y = Math.max(0, Math.min(this.height - b.h, Math.round(y)));
    // Custom boxes follow their captured OCR text as they're moved around.
    // PII-derived boxes keep their original span text.
    if (b.custom) b.text = this.textInBox(b.x, b.y, b.w, b.h);
  }

  // ── zoom ──────────────────────────────────────────────────────────
  zoomFit(containerW: number, containerH: number) {
    const pad = 72;
    const s = Math.min(1, (containerW - pad) / this.width, (containerH - pad) / this.height);
    this.scale = Math.max(0.1, s);
  }

  zoomReset() {
    this.scale = 1;
  }

  zoomStep(dir: number) {
    const steps = [0.1, 0.25, 0.33, 0.5, 0.67, 0.75, 1, 1.25, 1.5, 2, 3, 4];
    let i = steps.findIndex((s) => s >= this.scale - 0.001);
    if (i < 0) i = 0;
    i = Math.max(0, Math.min(steps.length - 1, i + dir));
    this.scale = steps[i];
  }

  /** Smooth multiplicative zoom — used by mouse-wheel / trackpad gestures. */
  zoomBy(factor: number) {
    this.scale = Math.max(0.1, Math.min(4, this.scale * factor));
  }

  // ── export ────────────────────────────────────────────────────────
  /** Render the active page (working copy) — used by the canvas overlay path. */
  renderExportCanvas(): HTMLCanvasElement {
    return this.#renderPageCanvas(this.img, this.width, this.height, this.boxes);
  }

  /**
   * Render any page by index. Reads from the live working copy when the
   * index matches activeIdx, so in-flight edits show up in the export.
   */
  renderPageCanvas(pageIdx: number): HTMLCanvasElement | null {
    const page = this.pages[pageIdx];
    if (!page) return null;
    if (pageIdx === this.activeIdx) {
      return this.#renderPageCanvas(this.img, this.width, this.height, this.boxes);
    }
    return this.#renderPageCanvas(page.img, page.width, page.height, page.boxes);
  }

  /** Small thumbnail render of a page with masks burned in (preview style). */
  renderThumbnailCanvas(pageIdx: number, maxSize = 240): HTMLCanvasElement | null {
    const page = this.pages[pageIdx];
    if (!page) return null;
    const source =
      pageIdx === this.activeIdx
        ? { img: this.img, w: this.width, h: this.height, boxes: this.boxes }
        : { img: page.img, w: page.width, h: page.height, boxes: page.boxes };
    if (!source.img) return null;
    const scale = Math.min(1, maxSize / Math.max(source.w, source.h));
    const tw = Math.max(1, Math.round(source.w * scale));
    const th = Math.max(1, Math.round(source.h * scale));
    const c = document.createElement('canvas');
    c.width = tw;
    c.height = th;
    const ctx = c.getContext('2d');
    if (!ctx) return c;
    ctx.drawImage(source.img, 0, 0, tw, th);
    ctx.fillStyle = this.maskColor;
    for (const b of source.boxes) {
      if (!this.isVisible(b)) continue;
      ctx.fillRect(b.x * scale, b.y * scale, b.w * scale, b.h * scale);
    }
    return c;
  }

  #renderPageCanvas(
    img: HTMLImageElement | null,
    width: number,
    height: number,
    boxes: EditorBox[],
  ): HTMLCanvasElement {
    const c = document.createElement('canvas');
    c.width = width;
    c.height = height;
    const ctx = c.getContext('2d');
    if (!ctx) return c;
    if (img) ctx.drawImage(img, 0, 0);
    ctx.fillStyle = this.maskColor;
    for (const b of boxes) {
      if (!this.isVisible(b)) continue;
      ctx.fillRect(b.x, b.y, b.w, b.h);
    }
    return c;
  }

  /** Render one page to a PNG Blob. */
  async pageToPngBlob(pageIdx: number): Promise<Blob | null> {
    const canvas = this.renderPageCanvas(pageIdx);
    if (!canvas) return null;
    return await new Promise<Blob | null>((resolve) =>
      canvas.toBlob((blob) => resolve(blob), 'image/png'),
    );
  }

  renderSanitizedText(): string {
    let out = '';
    let pos = 0;
    const spans = this.spans
      .filter((s) => this.activeCats.has(s.label))
      .toSorted((a, b) => a.start - b.start);
    for (const sp of spans) {
      if (sp.start < pos) continue;
      const tag = (this.catMeta[sp.label]?.label ?? sp.label).toLowerCase();
      out += `${this.sourceText.slice(pos, sp.start)}[${tag}]`;
      pos = sp.end;
    }
    out += this.sourceText.slice(pos);
    return out;
  }
}

export const editor = new EditorState();
