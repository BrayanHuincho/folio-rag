import { useState } from "react";
import { ChevronRight, Folder, HardDrive, Monitor } from "lucide-react";
import { api, type Collection } from "../api";
import { useAsync } from "../hooks";
import { basename } from "../format";

interface Props {
  onCreated: (c: Collection) => void;
  onCancel: () => void;
}

function crumbs(path: string): { label: string; path: string }[] {
  if (!path) return [];
  const sep = path.includes("\\") ? "\\" : "/";
  const parts = path.split(/[\\/]/).filter(Boolean);
  const out: { label: string; path: string }[] = [];
  let acc = path.startsWith("/") ? "/" : "";
  for (const part of parts) {
    acc = acc && !acc.endsWith(sep) ? `${acc}${sep}${part}` : `${acc}${part}`;
    // en Windows la raíz de unidad necesita la barra final: C:\
    out.push({ label: part, path: /^[A-Za-z]:$/.test(acc) ? `${acc}\\` : acc });
  }
  return out;
}

export default function FolderForm({ onCreated, onCancel }: Props) {
  const [path, setPath] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const browse = useAsync(() => api.browse(path), [path]);

  const current = browse.data?.path ?? "";
  const target = selected ?? current;

  const enter = (p: string) => {
    setSelected(null);
    setPath(p);
  };

  const submit = async () => {
    if (!target) return;
    setSaving(true);
    setError(null);
    try {
      onCreated(await api.createCollection(basename(target), target));
    } catch (err) {
      setError((err as Error).message);
      setSaving(false);
    }
  };

  const atRoot = !current;

  return (
    <div className="folder-form">
      <p className="hint">Folio lee la carpeta en su sitio, sin copiarla, y se mantiene al día cuando cambian los archivos.</p>
      <nav className="crumbs" aria-label="Ruta">
        <button type="button" onClick={() => enter("")}>
          <Monitor size={14} /> Este equipo
        </button>
        {crumbs(current).map((c) => (
          <span key={c.path} className="crumb">
            <ChevronRight size={13} />
            <button type="button" onClick={() => enter(c.path)}>{c.label}</button>
          </span>
        ))}
      </nav>

      <ul className="browser-list" role="listbox" aria-label="Carpetas">
        {browse.loading && <li className="browser-empty">Leyendo…</li>}
        {browse.error && <li className="browser-empty error-text">{browse.error}</li>}
        {!browse.loading && browse.data && !browse.data.dirs.length && (
          <li className="browser-empty">Esta carpeta no tiene subcarpetas. Puedes usarla tal cual.</li>
        )}
        {!browse.loading &&
          browse.data?.dirs.map((d) => (
            <li key={d.path}>
              <button
                type="button"
                role="option"
                aria-selected={selected === d.path}
                onClick={() => setSelected(d.path)}
                onDoubleClick={() => enter(d.path)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), enter(d.path))}
              >
                {atRoot ? <HardDrive size={16} /> : <Folder size={16} />}
                <span>{d.name}</span>
                <ChevronRight size={14} className="enter" onClick={(e) => (e.stopPropagation(), enter(d.path))} />
              </button>
            </li>
          ))}
      </ul>
      <p className="hint small">Doble clic para abrir una carpeta.</p>

      {error && <p className="form-error">{error}</p>}

      <div className="form-actions">
        <button type="button" className="btn" onClick={onCancel}>Cancelar</button>
        <button type="button" className="btn btn-primary" disabled={!target || saving} onClick={submit}>
          {saving ? "Añadiendo…" : target ? `Usar «${basename(target)}»` : "Usar esta carpeta"}
        </button>
      </div>
    </div>
  );
}
