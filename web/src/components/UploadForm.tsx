import { useState } from "react";
import { FileText, X } from "lucide-react";
import { api, type Collection, type UploadFile } from "../api";
import { bytes, plural } from "../format";
import { suggestedName } from "../files";
import Dropzone from "./Dropzone";

interface Props {
  onCreated: (c: Collection) => void;
  onCancel?: () => void;
  compact?: boolean;
}

export default function UploadForm({ onCreated, onCancel, compact }: Props) {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [name, setName] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const add = (more: UploadFile[]) => {
    setFiles((cur) => {
      const seen = new Set(cur.map((f) => f.path));
      const next = [...cur, ...more.filter((f) => !seen.has(f.path))];
      if (!name) setName(suggestedName(next));
      return next;
    });
    setError(null);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!files.length) return;
    setProgress(0);
    setError(null);
    try {
      onCreated(await api.uploadCollection(files, name.trim() || undefined, setProgress));
    } catch (err) {
      setError((err as Error).message);
      setProgress(null);
    }
  };

  const total = files.reduce((n, f) => n + f.file.size, 0);
  const uploading = progress !== null;

  return (
    <form onSubmit={submit} className="upload-form">
      <Dropzone onFiles={add} disabled={uploading} compact={compact || files.length > 0} />

      {files.length > 0 && (
        <div className="file-picks">
          <div className="file-picks-head">
            <span>
              {plural(files.length, "archivo", "archivos")}, {bytes(total)}
            </span>
            {!uploading && (
              <button type="button" className="link-btn" onClick={() => setFiles([])}>
                Quitar todos
              </button>
            )}
          </div>
          <ul>
            {files.slice(0, 50).map((f) => (
              <li key={f.path}>
                <FileText size={14} />
                <span title={f.path}>{f.path}</span>
                {!uploading && (
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => setFiles((cur) => cur.filter((x) => x.path !== f.path))}
                    aria-label={`Quitar ${f.path}`}
                  >
                    <X size={13} />
                  </button>
                )}
              </li>
            ))}
            {files.length > 50 && <li className="muted">y {files.length - 50} más</li>}
          </ul>
        </div>
      )}

      <label className="field">
        <span>Nombre (opcional)</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Por ejemplo, Contratos 2024" disabled={uploading} />
      </label>

      {uploading && (
        <div className="upload-progress">
          <div className="bar"><span style={{ width: `${Math.round(progress * 100)}%` }} /></div>
          <span>{progress < 1 ? `Subiendo… ${Math.round(progress * 100)} %` : "Procesando en el servidor…"}</span>
        </div>
      )}
      {error && <p className="form-error">{error}</p>}

      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn" onClick={onCancel} disabled={uploading}>
            Cancelar
          </button>
        )}
        <button type="submit" className="btn btn-primary" disabled={!files.length || uploading}>
          {uploading ? "Subiendo…" : "Agregar carpeta"}
        </button>
      </div>
    </form>
  );
}
