import { useDeferredValue, useRef, useState } from "react";
import { LayoutGrid, List, Plus, Search } from "lucide-react";
import { api, type Collection, type DocumentStatus, type UploadFile } from "../api";
import { useAsync, useStoredState } from "../hooks";
import Thumb from "./Thumb";
import { extOf } from "./FileCard";
import { bytes, plural, relativeTime } from "../format";
import { fromInput } from "../files";

const statusLabel: Record<DocumentStatus, string> = {
  indexed: "Indexado",
  pending: "En cola",
  skipped: "Omitido",
  error: "Error",
};

interface Props {
  collection: Collection;
  onOpen: (id: string) => void;
  onAttach: (files: UploadFile[]) => void;
}

export default function DocumentsView({ collection, onOpen, onAttach }: Props) {
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query);
  const picker = useRef<HTMLInputElement>(null);
  const [view, setView] = useStoredState<"list" | "grid">("folio.docview", "list");
  const docs = useAsync(() => api.documents(collection.id, deferred), [collection.id, deferred, collection.updated_at]);
  const rows = docs.data ?? [];
  const failed = rows.filter((d) => d.status === "error").length;

  return (
    <div className="documents">
      <div className="documents-inner">
        <div className="documents-head">
          <div>
            <h1>{collection.name}</h1>
            <p className="muted">
              {plural(collection.doc_count, "documento", "documentos")}, {plural(collection.chunk_count, "fragmento", "fragmentos")},{" "}
              {bytes(collection.size_bytes)}
              {failed > 0 && <span className="error-text">. {plural(failed, "archivo no se pudo leer", "archivos no se pudieron leer")}</span>}
            </p>
            {!collection.managed && <p className="path">{collection.path}</p>}
          </div>
          <div className="documents-tools">
            <label className="search">
              <Search size={15} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar por nombre" aria-label="Buscar documentos" />
            </label>
            <div className="view-toggle" role="radiogroup" aria-label="Vista">
              <button role="radio" aria-checked={view === "list"} onClick={() => setView("list")} title="Lista" aria-label="Lista">
                <List size={16} />
              </button>
              <button role="radio" aria-checked={view === "grid"} onClick={() => setView("grid")} title="Cuadrícula" aria-label="Cuadrícula">
                <LayoutGrid size={16} />
              </button>
            </div>
            <button className="btn" onClick={() => picker.current?.click()}>
              <Plus size={15} /> Añadir archivos
            </button>
            <input
              ref={picker}
              type="file"
              multiple
              hidden
              onChange={(e) => {
                const files = fromInput(e.target.files);
                if (files.length) onAttach(files);
                e.target.value = "";
              }}
            />
          </div>
        </div>

        {docs.error && <p className="error-text">{docs.error}</p>}
        {!docs.loading && !rows.length && !docs.error && (
          <p className="muted empty-table">{query ? `Ningún documento coincide con «${query}».` : "Todavía no hay documentos indexados."}</p>
        )}

        {rows.length > 0 && view === "grid" && (
          <ul className="doc-grid">
            {rows.map((d) => (
              <li key={d.id}>
                <button className="doc-tile" onClick={() => onOpen(d.id)} title={d.rel_path}>
                  <Thumb ext={extOf(d.rel_path)} url={api.rawUrl(d.id)} />
                  <span className="doc-tile-name">{d.rel_path.split("/").pop()}</span>
                  <span className="status" data-status={d.status}>{statusLabel[d.status] ?? d.status}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {rows.length > 0 && view === "list" && (
          <div>
            <table className="doc-table">
              <thead>
                <tr>
                  <th>Archivo</th>
                  <th>Estado</th>
                  <th className="num">Fragmentos</th>
                  <th className="num hide-sm">Tamaño</th>
                  <th className="hide-sm">Indexado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id} onClick={() => onOpen(d.id)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onOpen(d.id)}>
                    <td className="doc-path">
                      <span>{d.rel_path}</span>
                      {d.error && <small className="error-text">{d.error}</small>}
                    </td>
                    <td>
                      <span className="status" data-status={d.status}>{statusLabel[d.status] ?? d.status}</span>
                    </td>
                    <td className="num">{d.chunk_count}</td>
                    <td className="num hide-sm">{bytes(d.size)}</td>
                    <td className="hide-sm muted">{d.indexed_at ? relativeTime(d.indexed_at) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
