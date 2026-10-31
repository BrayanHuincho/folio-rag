import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { openPdf } from "../thumbs";

// renderizamos con pdf.js en vez del visor del navegador para poder saltar a la página citada siempre
export default function PdfPreview({ url, page }: { url: string; page: number | null }) {
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    let destroy: (() => void) | undefined;
    openPdf(url)
      .then((task) => {
        destroy = () => task.destroy();
        return task.promise;
      })
      .then((d) => live && setDoc(d))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
      destroy?.();
    };
  }, [url]);

  if (error) return <p className="error-text preview-pad">No se pudo abrir el PDF: {error}</p>;
  if (!doc) return <div className="skeleton-lines tall preview-pad" aria-hidden><span /><span /><span /></div>;

  return (
    <div className="pdf-pages">
      {Array.from({ length: doc.numPages }, (_, i) => (
        <PdfPage key={i} doc={doc} n={i + 1} focus={page === i + 1} />
      ))}
    </div>
  );
}

function PdfPage({ doc, n, focus }: { doc: PDFDocumentProxy; n: number; focus: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [visible, setVisible] = useState(focus || n === 1);
  const [ratio, setRatio] = useState(1.414);

  useEffect(() => {
    if (focus) box.current?.scrollIntoView({ block: "start" });
  }, [focus]);

  useEffect(() => {
    if (visible || !box.current) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setVisible(true), { rootMargin: "600px" });
    io.observe(box.current);
    return () => io.disconnect();
  }, [visible]);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    let task: { cancel: () => void } | undefined;
    doc.getPage(n).then((p) => {
      if (cancelled || !canvas.current || !box.current) return;
      const base = p.getViewport({ scale: 1 });
      setRatio(base.height / base.width);
      const scale = (box.current.clientWidth * window.devicePixelRatio) / base.width;
      const viewport = p.getViewport({ scale });
      canvas.current.width = Math.floor(viewport.width);
      canvas.current.height = Math.floor(viewport.height);
      const render = p.render({ canvas: canvas.current, viewport });
      task = render;
      render.promise.catch(() => undefined);
    });
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [visible, doc, n]);

  return (
    <div className="pdf-page" ref={box} style={{ aspectRatio: `1 / ${ratio}` }} data-focus={focus || undefined}>
      <canvas ref={canvas} />
      <span className="pdf-page-n">{n}</span>
    </div>
  );
}
