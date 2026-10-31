import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type DocumentDetail } from "../api";
import { useAsync } from "../hooks";
import { isImage } from "../thumbs";
import PdfPreview from "./PdfPreview";

const codeExts = new Set([
  "txt", "log", "json", "yaml", "yml", "toml", "ini", "cfg", "env", "xml", "sql", "sh", "ps1", "bat",
  "py", "js", "jsx", "ts", "tsx", "java", "kt", "go", "rs", "rb", "php", "c", "h", "cpp", "hpp", "cs",
  "swift", "css", "scss", "vue", "svelte", "r", "lua", "dart",
]);

export type PreviewKind = "pdf" | "image" | "docx" | "table" | "slides" | "markdown" | "code" | "html" | null;

export function previewKind(ext: string): PreviewKind {
  if (ext === "pdf") return "pdf";
  if (isImage(ext)) return "image";
  if (ext === "docx") return "docx";
  if (["xlsx", "xlsm", "csv", "tsv"].includes(ext)) return "table";
  if (ext === "pptx") return "slides";
  if (ext === "md" || ext === "markdown") return "markdown";
  if (ext === "html" || ext === "htm") return "html";
  if (codeExts.has(ext)) return "code";
  return null;
}

interface Props {
  doc: DocumentDetail;
  kind: Exclude<PreviewKind, null>;
  page: number | null;
}

export default function Preview({ doc, kind, page }: Props) {
  const raw = api.rawUrl(doc.id);
  switch (kind) {
    case "pdf":
      return <PdfPreview url={raw} page={page} />;
    case "html":
      return <iframe className="preview-frame light" src={raw} sandbox="" title={doc.rel_path} />;
    case "image":
      return <ImagePreview src={raw} />;
    case "docx":
      return <DocxPreview id={doc.id} />;
    case "table":
      return <TablePreview id={doc.id} />;
    case "slides":
      return <SlidesPreview doc={doc} page={page} />;
    case "markdown":
      return <TextPreview id={doc.id} markdown />;
    case "code":
      return <TextPreview id={doc.id} />;
  }
}

function Loading() {
  return <div className="skeleton-lines tall preview-pad" aria-hidden><span /><span /><span /><span /></div>;
}

function Failed({ message }: { message: string }) {
  return <p className="error-text preview-pad">No se pudo mostrar la vista previa: {message}</p>;
}

function ImagePreview({ src }: { src: string }) {
  const [zoom, setZoom] = useState(false);
  return (
    <div className="preview-image" data-zoom={zoom || undefined}>
      <img src={src} alt="" onClick={() => setZoom((z) => !z)} title={zoom ? "Ajustar a la ventana" : "Ampliar"} />
    </div>
  );
}

function DocxPreview({ id }: { id: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ok" | string>("loading");

  useEffect(() => {
    let live = true;
    Promise.all([api.rawBlob(id), import("docx-preview")])
      .then(async ([blob, lib]) => {
        if (!live || !box.current) return;
        box.current.innerHTML = "";
        await lib.renderAsync(blob, box.current, undefined, { inWrapper: true, ignoreLastRenderedPageBreak: true });
        if (live) setState("ok");
      })
      .catch((e: Error) => live && setState(e.message));
    return () => {
      live = false;
    };
  }, [id]);

  return (
    <div className="preview-docx">
      {state === "loading" && <Loading />}
      {state !== "loading" && state !== "ok" && <Failed message={state} />}
      <div ref={box} />
    </div>
  );
}

function columnName(i: number): string {
  let name = "";
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) name = String.fromCharCode(65 + ((n - 1) % 26)) + name;
  return name;
}

function TablePreview({ id }: { id: string }) {
  const { data, error, loading } = useAsync(() => api.table(id), [id]);
  const [sheet, setSheet] = useState(0);
  if (loading) return <Loading />;
  if (error || !data) return <Failed message={error ?? "sin datos"} />;
  const current = data.sheets[sheet] ?? data.sheets[0];
  if (!current) return <p className="muted preview-pad">La hoja está vacía.</p>;

  const [head = [], ...rows] = current.rows;
  const width = Math.max(head.length, ...rows.map((r) => r.length));
  const cols = Array.from({ length: width }, (_, i) => i);

  return (
    <div className="sheet">
      <div className="sheet-scroll">
        <table>
          <thead>
            <tr className="sheet-letters">
              <th className="corner" />
              {cols.map((c) => <th key={c}>{columnName(c)}</th>)}
            </tr>
            <tr className="sheet-head">
              <th className="row-num">1</th>
              {cols.map((c) => <th key={c}>{head[c] ?? ""}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <th className="row-num">{i + 2}</th>
                {cols.map((c) => <td key={c}>{r[c] ?? ""}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="sheet-foot">
        <div className="sheet-tabs" role="tablist">
          {data.sheets.map((s, i) => (
            <button key={s.name + i} role="tab" aria-selected={i === sheet} onClick={() => setSheet(i)}>
              {s.name}
            </button>
          ))}
        </div>
        {current.truncated && <span className="muted">Mostrando primeras {data.max_rows.toLocaleString("es")} filas</span>}
      </div>
    </div>
  );
}

function SlidesPreview({ doc, page }: { doc: DocumentDetail; page: number | null }) {
  const slides = new Map<number, string[]>();
  for (const ch of doc.chunks) {
    const n = ch.page ?? slides.size + 1;
    slides.set(n, [...(slides.get(n) ?? []), ch.text]);
  }
  const focus = useRef<HTMLElement>(null);
  useEffect(() => focus.current?.scrollIntoView({ block: "center" }), [page]);

  if (!slides.size) return <p className="muted preview-pad">Esta presentación no tiene texto indexado.</p>;
  return (
    <div className="slides">
      {[...slides.entries()].sort(([a], [b]) => a - b).map(([n, texts]) => (
        <section key={n} className="slide" ref={n === page ? focus : undefined} data-focus={n === page || undefined}>
          <span className="slide-n">Diapositiva {n}</span>
          <div className="slide-body">{texts.join("\n\n")}</div>
        </section>
      ))}
    </div>
  );
}

function TextPreview({ id, markdown }: { id: string; markdown?: boolean }) {
  const { data, error, loading } = useAsync(() => api.rawText(id), [id]);
  if (loading) return <Loading />;
  if (error || data === null) return <Failed message={error ?? "sin datos"} />;
  if (markdown) {
    return (
      <div className="prose preview-pad">
        <Markdown remarkPlugins={[remarkGfm]}>{data}</Markdown>
      </div>
    );
  }
  const lines = data.replace(/\n$/, "").split("\n");
  return (
    <div className="code-view">
      <pre>
        {lines.map((line, i) => (
          <span key={i} className="code-line">
            <span className="ln">{i + 1}</span>
            <span>{line || " "}</span>
          </span>
        ))}
      </pre>
    </div>
  );
}
