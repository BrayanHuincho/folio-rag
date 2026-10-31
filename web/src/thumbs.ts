const imageExts = new Set(["png", "jpg", "jpeg", "webp", "gif", "svg", "bmp"]);

export const isImage = (ext: string) => imageExts.has(ext);
export const isPdf = (ext: string) => ext === "pdf";

let pdfjs: Promise<typeof import("pdfjs-dist")> | null = null;

// pdfjs pesa bastante, solo se carga cuando hace falta una miniatura o una vista
function loadPdfjs() {
  pdfjs ??= Promise.all([import("pdfjs-dist"), import("pdfjs-dist/build/pdf.worker.min.mjs?url")]).then(
    ([lib, worker]) => {
      lib.GlobalWorkerOptions.workerSrc = worker.default;
      return lib;
    },
  );
  return pdfjs;
}

export async function openPdf(url: string) {
  const lib = await loadPdfjs();
  return lib.getDocument({ url });
}

const cache = new Map<string, Promise<string>>();

export function pdfThumbnail(source: File | string, width = 320): Promise<string> {
  const key = typeof source === "string" ? source : `${source.name}:${source.size}:${source.lastModified}`;
  let job = cache.get(key);
  if (!job) {
    job = render(source, width);
    cache.set(key, job);
    job.catch(() => cache.delete(key));
  }
  return job;
}

async function render(source: File | string, width: number): Promise<string> {
  const lib = await loadPdfjs();
  const data = typeof source === "string" ? { url: source } : { data: new Uint8Array(await source.arrayBuffer()) };
  const task = lib.getDocument(data);
  const doc = await task.promise;
  try {
    const page = await doc.getPage(1);
    const base = page.getViewport({ scale: 1 });
    const viewport = page.getViewport({ scale: width / base.width });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    await page.render({ canvas, viewport }).promise;
    return canvas.toDataURL("image/jpeg", 0.82);
  } finally {
    task.destroy();
  }
}
