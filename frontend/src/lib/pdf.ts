// PDF rasterization helper — converts a PDF into one image File per page,
// so the existing image pipeline (engine.analyze) handles pages uniformly.
// pdfjs-dist worker is loaded as a Vite ?url asset so it ships with the SPA.
import * as pdfjs from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

/** Rasterize each PDF page at the given scale and return one PNG `File` per page. */
export async function pdfToImageFiles(file: File, scale = 2): Promise<File[]> {
  const data = await file.arrayBuffer();
  const pdf = await pdfjs.getDocument({ data }).promise;
  const base = file.name.replace(/\.pdf$/i, '');
  const out: File[] = [];

  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const viewport = page.getViewport({ scale });
    const canvas = document.createElement('canvas');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('canvas 2d context unavailable');
    await page.render({ canvasContext: ctx, viewport, canvas }).promise;
    const blob: Blob = await new Promise((res, rej) => {
      canvas.toBlob((b) => (b ? res(b) : rej(new Error('toBlob returned null'))), 'image/png');
    });
    out.push(new File([blob], `${base}-p${i}.png`, { type: 'image/png' }));
  }
  return out;
}

export function isPdf(file: File): boolean {
  return file.type === 'application/pdf' || /\.pdf$/i.test(file.name);
}
