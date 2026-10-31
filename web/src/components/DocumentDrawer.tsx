import { useEffect, useRef, useState } from "react";
import { Download, ExternalLink, X } from "lucide-react";
import { api, type DocumentDetail } from "../api";
import { useAsync } from "../hooks";
import { basename, dirname } from "../format";
import { extOf } from "./FileCard";
import { TypeTile } from "./Thumb";
import Preview, { previewKind } from "./Preview";

export interface DrawerTarget {
  documentId: string;
  chunkId?: string;
}

type Tab = "preview" | "text";

export default function DocumentDrawer({ target, onClose }: { target: DrawerTarget; onClose: () => void }) {
  const doc = useAsync(() => api.document(target.documentId), [target.documentId]);
  const ext = doc.data ? extOf(doc.data.rel_path) : "";
  const kind = previewKind(ext);
  const [tab, setTab] = useState<Tab>("preview");
  const showing: Tab = kind ? tab : "text";
  const page = doc.data?.chunks.find((c) => c.id === target.chunkId)?.page ?? null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const raw = api.rawUrl(target.documentId);

  return (
    <div className="drawer-layer" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Documento">
        <header className="drawer-head">
          {doc.data && <TypeTile ext={ext} />}
          <div className="drawer-title">
            <h2>{doc.data ? basename(doc.data.rel_path) : "Abriendo…"}</h2>
            {doc.data && <span className="path">{dirname(doc.data.rel_path) || "Carpeta principal"}</span>}
          </div>
          <div className="drawer-actions">
            <a className="btn btn-small" href={raw} target="_blank" rel="noreferrer">
              <ExternalLink size={14} /> <span className="hide-sm">Abrir archivo</span>
            </a>
            <a className="btn btn-small" href={raw} download={doc.data ? basename(doc.data.rel_path) : true}>
              <Download size={14} /> <span className="hide-sm">Descargar</span>
            </a>
            <button className="icon-btn" onClick={onClose} aria-label="Cerrar">
              <X size={18} />
            </button>
          </div>
        </header>

        {kind && (
          <nav className="drawer-tabs" role="tablist">
            <button role="tab" aria-selected={showing === "preview"} onClick={() => setTab("preview")}>Vista previa</button>
            <button role="tab" aria-selected={showing === "text"} onClick={() => setTab("text")}>Texto</button>
          </nav>
        )}

        <div className="drawer-body" data-tab={showing}>
          {doc.loading && <div className="skeleton-lines tall preview-pad" aria-hidden><span /><span /><span /><span /></div>}
          {doc.error && <p className="error-text preview-pad">{doc.error}</p>}
          {doc.data && kind && showing === "preview" && <Preview doc={doc.data} kind={kind} page={page} />}
          {doc.data && showing === "text" && <ChunkText doc={doc.data} chunkId={target.chunkId} />}
        </div>
      </aside>
    </div>
  );
}

function ChunkText({ doc, chunkId }: { doc: DocumentDetail; chunkId?: string }) {
  const focused = useRef<HTMLElement>(null);
  useEffect(() => focused.current?.scrollIntoView({ block: "center" }), [chunkId]);

  if (!doc.chunks.length) {
    return <p className="muted preview-pad">Este archivo no tiene texto indexado{doc.error ? `: ${doc.error}` : "."}</p>;
  }
  return (
    <div className="chunks">
      {doc.chunks.map((ch, i) => {
        const prev = doc.chunks[i - 1];
        const isFocus = ch.id === chunkId;
        return (
          <section key={ch.id} ref={isFocus ? focused : undefined} className="passage" data-focus={isFocus || undefined}>
            {ch.page !== null && ch.page !== prev?.page && <span className="passage-page">Página {ch.page}</span>}
            {ch.heading && ch.heading !== prev?.heading && <h3>{ch.heading}</h3>}
            <p>{ch.text}</p>
          </section>
        );
      })}
    </div>
  );
}
