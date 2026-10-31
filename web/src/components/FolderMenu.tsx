import { useEffect, useRef } from "react";
import { Check, ChevronDown, Folder, FolderPlus, Layers } from "lucide-react";
import type { Collection } from "../api";
import { plural } from "../format";

export function FolderIcon({ c, size = 16 }: { c: Collection; size?: number }) {
  return c.managed ? <Layers size={size} /> : <Folder size={size} />;
}

export function folderStatus(c: Collection, progressText?: string | null): string {
  if (c.status === "indexing") return progressText ?? "Indexando…";
  if (c.status === "error") return "Error al indexar";
  return plural(c.doc_count, "documento", "documentos");
}

interface Props {
  collections: Collection[];
  current: Collection | undefined;
  progressText: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (id: string) => void;
  onAdd: () => void;
}

export default function FolderMenu({ collections, current, progressText, open, onOpenChange, onSelect, onAdd }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && onOpenChange(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onOpenChange(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open, onOpenChange]);

  return (
    <div className="folder-menu" ref={ref}>
      <button className="folder-pill" onClick={() => onOpenChange(!open)} aria-expanded={open}>
        {current ? <FolderIcon c={current} /> : <Folder size={16} />}
        <span className="ellipsis">
          {current ? (
            <>
              {current.name} <em>· {folderStatus(current, progressText)}</em>
            </>
          ) : (
            "Elegir carpeta"
          )}
        </span>
        {current?.status === "indexing" ? <span className="spinner" /> : <ChevronDown size={15} />}
      </button>
      {open && (
        <div className="popover folder-list" role="menu">
          <div className="popover-label">Carpetas</div>
          {collections.map((c) => (
            <button
              key={c.id}
              role="menuitemradio"
              aria-checked={c.id === current?.id}
              onClick={() => {
                onOpenChange(false);
                onSelect(c.id);
              }}
            >
              <FolderIcon c={c} size={18} />
              <span className="grow">
                <span className="ellipsis block">{c.name}</span>
                <small data-error={c.status === "error" || undefined}>{folderStatus(c, c.id === current?.id ? progressText : null)}</small>
              </span>
              {c.id === current?.id && <Check size={16} />}
            </button>
          ))}
          <div className="popover-sep" />
          <button role="menuitem" className="accent" onClick={() => (onOpenChange(false), onAdd())}>
            <FolderPlus size={18} /> Agregar carpeta…
          </button>
        </div>
      )}
    </div>
  );
}
