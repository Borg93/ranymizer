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
import type {
  AnonymizeResult,
  CatMeta,
  DragState,
  EditorBox,
  Mode,
  OcrLine,
  PiiSpan,
  View,
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
};

export class EditorState {
  // ── view / lifecycle ──────────────────────────────────────────────
  view = $state<View>('landing');
  loading = $state(false);
  loadingMessage = $state(''); // local-engine status / model-download text
  loadingProgress = $state<{ done: number; total: number } | null>(null);
  error = $state<string | null>(null);

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
  // Preview-only: paint boxes with category colors at maskAlpha so users can
  // see *why* each region was redacted. Never applied to the export canvas.
  showCategoryColors = $state(false);
  maskAlpha = $state(0.6);
  // Solid mask color used when `showCategoryColors` is off and in the export
  // (the downloaded PNG always uses this color, never the per-category tint).
  maskColor = $state('#000000');
  // Default category for the next drawn box.
  drawLabel = $state('custom');
  // Thumbnail carousel visibility — only matters when there are >1 pages.
  showThumbnails = $state(true);
  catMeta = $state<Record<string, CatMeta>>({});
  activeCats = new SvelteSet<string>();

  // ── editor tool state ─────────────────────────────────────────────
  mode = $state<Mode>('select');
  scale = $state(1);
  selected = $state<number | null>(null);
  drag = $state<DragState | null>(null);
  cursor = $state<{ x: number; y: number } | null>(null);

  // ── multi-page ────────────────────────────────────────────────────
  pages = $state<Page[]>([]);
  activeIdx = $state(0);

  // ── non-reactive bookkeeping ──────────────────────────────────────
  #nextId = 1;
  #uploadId = 0;
  #objectUrls: string[] = [];

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
    this.view = 'editor';
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

    const catMetaPromise = engine.meta().catch(() => ({}) as Record<string, CatMeta>);
    const firstNewIdx = this.pages.length;

    for (let i = 0; i < expanded.length; i++) {
      if (myId !== this.#uploadId) return;
      const file = expanded[i];
      this.loadingProgress = { done: i, total: expanded.length };
      this.loadingMessage = `Analysing ${i + 1}/${expanded.length}: ${file.name}`;

      const objectUrl = URL.createObjectURL(file);
      this.#objectUrls.push(objectUrl);

      try {
        const [img, result] = await Promise.all([
          this.#loadImage(objectUrl),
          engine.analyze(file, (p) => {
            if (myId !== this.#uploadId) return;
            if (p.phase === 'loading') {
              this.loadingMessage =
                p.percent != null ? `${p.message} ${Math.round(p.percent)}%` : p.message;
            }
          }),
        ]);

        if (myId !== this.#uploadId) return;
        if (result.error) {
          console.error('analyse failed for', file.name, '—', result.error);
          continue;
        }
        if (!result.filename) result.filename = file.name;

        const page = this.#resultToPage(result, img, objectUrl);
        this.pages = [...this.pages, page];

        // Union-in this page's categories.
        for (const b of page.boxes) {
          if (!b.custom) this.activeCats.add(b.label);
        }

        // Show the first newly-analysed page as soon as it's ready.
        // (In append mode this jumps from the previous page to the new one.)
        if (this.pages.length === firstNewIdx + 1) {
          if (Object.keys(this.catMeta).length === 0) {
            this.catMeta = await catMetaPromise;
          }
          this.activeIdx = firstNewIdx;
          this.#loadActivePage();
        }
      } catch (e) {
        if (myId !== this.#uploadId) return;
        const msg = e instanceof Error ? e.message : String(e);
        console.error('analyse failed for', file.name, '—', msg);
      }
    }

    if (myId !== this.#uploadId) return;
    this.loadingProgress = null;
    this.loading = false;
    this.loadingMessage = '';
    if (this.pages.length === 0) this.error = 'no pages could be analysed';
  }

  #resultToPage(r: AnonymizeResult, img: HTMLImageElement, objectUrl: string): Page {
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
    };
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
    this.selected = null;
    this.drag = null;
  }

  goTo(idx: number) {
    if (idx < 0 || idx >= this.pages.length || idx === this.activeIdx) return;
    this.#saveActivePage();
    this.activeIdx = idx;
    this.#loadActivePage();
  }

  prev() {
    this.goTo(this.activeIdx - 1);
  }
  next() {
    this.goTo(this.activeIdx + 1);
  }

  reset() {
    this.#uploadId++;
    this.#revokeAllObjectUrls();

    this.pages = [];
    this.activeIdx = 0;
    this.view = 'landing';
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
    this.boxes = this.boxes.filter((b) => b.id !== this.selected);
    this.selected = null;
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
    if (!b) return;
    b.text = text;
  }

  /** Reassign a box's category. Preserves the `custom` flag so visibility
   *  doesn't flip based on the category filter. */
  setBoxLabel(id: number, label: string) {
    const b = this.boxes.find((b) => b.id === id);
    if (!b) return;
    b.label = label;
    if (label !== 'custom') this.activeCats.add(label);
  }

  removeBox(id: number) {
    this.boxes = this.boxes.filter((b) => b.id !== id);
    if (this.selected === id) this.selected = null;
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
  renderExportCanvas(): HTMLCanvasElement {
    const c = document.createElement('canvas');
    c.width = this.width;
    c.height = this.height;
    const ctx = c.getContext('2d');
    if (!ctx) return c;
    if (this.img) ctx.drawImage(this.img, 0, 0);
    ctx.fillStyle = this.maskColor;
    for (const b of this.boxes) {
      if (!this.isVisible(b)) continue;
      ctx.fillRect(b.x, b.y, b.w, b.h);
    }
    return c;
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
