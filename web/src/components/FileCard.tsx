import { X } from "lucide-react";
import { basename, bytes } from "../format";
import Thumb, { TypeTile } from "./Thumb";

export function extOf(path: string): string {
  const name = basename(path);
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : "";
}

export function describe(path: string, size: number): string {
  const ext = extOf(path);
  return `${ext ? ext.toUpperCase() : "Archivo"}, ${bytes(size)}`;
}

export type FileState = "uploading" | "indexing" | "ready" | "error";

interface Props {
  path: string;
  file?: File;
  url?: string;
  state?: FileState;
  progress?: number;
  error?: string;
  onOpen?: () => void;
  onRemove?: () => void;
}

export default function FileCard({ path, file, url, state = "ready", progress = 0, error, onOpen, onRemove }: Props) {
  const ext = extOf(path);
  const body = (
    <>
      <Thumb ext={ext} file={file} url={url} />
      <span className="file-caption">
        <TypeTile ext={ext} />
        <span className="file-name">{basename(path)}</span>
      </span>
      {state === "uploading" && (
        <span className="file-progress" aria-label={`Subiendo, ${Math.round(progress * 100)} %`}>
          <span style={{ width: `${Math.max(4, Math.round(progress * 100))}%` }} />
        </span>
      )}
      {state === "indexing" && (
        <span className="file-badge">
          <span className="spinner" aria-hidden /> Indexando…
        </span>
      )}
      {state === "error" && <span className="file-badge error">{error || "Error"}</span>}
    </>
  );

  return (
    <div className="file-card" data-state={state} title={error ?? path}>
      {onOpen ? (
        <button className="file-main" onClick={onOpen}>{body}</button>
      ) : (
        <span className="file-main">{body}</span>
      )}
      {onRemove && (
        <button className="file-remove" onClick={onRemove} aria-label={`Quitar ${basename(path)}`}>
          <X size={12} strokeWidth={2.5} />
        </button>
      )}
    </div>
  );
}
