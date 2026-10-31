import { useEffect, useRef, useState } from "react";
import {
  FileStack,
  FolderPlus,
  MoreHorizontal,
  PanelLeftClose,
  Pencil,
  RefreshCw,
  Search,
  SquarePen,
  Trash2,
} from "lucide-react";
import { api, type Collection, type ConversationSummary } from "../api";
import { useAsync } from "../hooks";
import { dateGroup, type DateGroup } from "../format";
import { FolderIcon, folderStatus } from "./FolderMenu";

interface Props {
  collections: Collection[];
  current: Collection | undefined;
  progressText: string | null;
  conversationId: string | null;
  convVersion: number;
  documentsActive: boolean;
  modelName: string;
  onSelectCollection: (id: string) => void;
  onSelectConversation: (id: string) => void;
  onConversationDeleted: (id: string) => void;
  onNewChat: () => void;
  onDocuments: () => void;
  onNewCollection: () => void;
  onChanged: () => void;
  onClose: () => void;
}

function useOutside<T extends HTMLElement>(open: boolean, close: () => void) {
  const ref = useRef<T>(null);
  const closeRef = useRef(close);
  closeRef.current = close;
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && closeRef.current();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return ref;
}

export default function Sidebar(props: Props) {
  const { current } = props;
  const [searching, setSearching] = useState(false);
  const [filter, setFilter] = useState("");

  const toggleSearch = () => {
    setSearching((s) => !s);
    setFilter("");
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <span className="brand">
          <span className="logo" aria-hidden>F</span>
          Folio
        </span>
        <button className="icon-btn" onClick={props.onClose} aria-label="Cerrar barra lateral" title="Cerrar barra lateral">
          <PanelLeftClose size={18} />
        </button>
      </div>

      <nav className="nav">
        <button className="nav-row" onClick={props.onNewChat} disabled={!current}>
          <SquarePen size={18} /> <span>Nueva conversación</span> <kbd>Ctrl K</kbd>
        </button>
        <button className="nav-row" aria-pressed={searching} onClick={toggleSearch} disabled={!current}>
          <Search size={18} /> <span>Buscar chats</span>
        </button>
        <button className="nav-row" aria-current={props.documentsActive || undefined} onClick={props.onDocuments} disabled={!current}>
          <FileStack size={18} /> <span>Documentos</span>
        </button>
      </nav>

      <div className="sidebar-scroll">
        <h3 className="side-label">Carpetas</h3>
        <ul className="side-list">
          {props.collections.map((c) => (
            <FolderRow
              key={c.id}
              c={c}
              selected={c.id === current?.id}
              status={folderStatus(c, c.id === current?.id ? props.progressText : null)}
              onSelect={() => props.onSelectCollection(c.id)}
              onChanged={props.onChanged}
            />
          ))}
          <li>
            <button className="nav-row add-folder" onClick={props.onNewCollection}>
              <FolderPlus size={17} /> <span>Agregar carpeta</span>
            </button>
          </li>
        </ul>
        {current && <h3 className="side-label recent-label">Recientes</h3>}
        {current && (
          <History
            key={current.id}
            collectionId={current.id}
            version={props.convVersion}
            activeId={props.documentsActive ? null : props.conversationId}
            searching={searching}
            filter={filter}
            onFilter={setFilter}
            onSelect={props.onSelectConversation}
            onDeleted={props.onConversationDeleted}
          />
        )}
      </div>

      <div className="sidebar-foot">
        <span className="user-avatar" aria-hidden>F</span>
        <span className="foot-text">
          <strong>Folio</strong>
          <small title={props.modelName}>Local · {props.modelName || "sin modelo"}</small>
        </span>
      </div>
    </aside>
  );
}

function FolderRow({ c, selected, status, onSelect, onChanged }: { c: Collection; selected: boolean; status: string; onSelect: () => void; onChanged: () => void }) {
  const [menu, setMenu] = useState(false);
  const ref = useOutside<HTMLLIElement>(menu, () => setMenu(false));

  const act = async (fn: () => Promise<void>) => {
    setMenu(false);
    await fn().catch(() => undefined);
    onChanged();
  };

  return (
    <li className="side-item folder-row" aria-current={selected || undefined} data-menu={menu || undefined} ref={ref}>
      <button className="side-link folder-link" onClick={onSelect} title={c.managed ? c.name : c.path}>
        <FolderIcon c={c} size={17} />
        <span className="ellipsis">{c.name}</span>
        {c.status === "indexing" ? <span className="spinner" /> : <small className="folder-count">{c.status === "error" ? "Error" : c.doc_count}</small>}
      </button>
      <button className="row-more" onClick={() => setMenu((m) => !m)} aria-label={`Opciones de ${c.name}`}>
        <MoreHorizontal size={16} />
      </button>
      {menu && (
        <div className="popover row-menu" role="menu">
          <p className="popover-empty">{status}</p>
          <button role="menuitem" onClick={() => act(() => api.reindex(c.id, true))}>
            <RefreshCw size={16} /> Volver a indexar
          </button>
          <button
            role="menuitem"
            className="danger"
            onClick={() => {
              const warn = c.managed
                ? `¿Eliminar la carpeta «${c.name}»? Se borrarán los archivos subidos.`
                : `¿Quitar «${c.name}» de Folio? Tus archivos no se tocan.`;
              if (confirm(warn)) act(() => api.deleteCollection(c.id));
            }}
          >
            <Trash2 size={16} /> Quitar carpeta
          </button>
        </div>
      )}
    </li>
  );
}
const groupOrder: DateGroup[] = ["Hoy", "Ayer", "Últimos 7 días", "Anteriores"];

interface HistoryProps {
  collectionId: string;
  version: number;
  activeId: string | null;
  searching: boolean;
  filter: string;
  onFilter: (v: string) => void;
  onSelect: (id: string) => void;
  onDeleted: (id: string) => void;
}

function History({ collectionId, version, activeId, searching, filter, onFilter, onSelect, onDeleted }: HistoryProps) {
  const { data, loading, setData } = useAsync(() => api.conversations(collectionId), [collectionId, version]);
  const list = data ?? [];
  const needle = filter.trim().toLowerCase();
  const shown = needle ? list.filter((c) => (c.title ?? "").toLowerCase().includes(needle)) : list;

  const groups = new Map<DateGroup, ConversationSummary[]>();
  for (const c of shown) {
    const g = dateGroup(c.updated_at);
    groups.set(g, [...(groups.get(g) ?? []), c]);
  }

  const remove = async (id: string) => {
    await api.deleteConversation(id).catch(() => undefined);
    setData(list.filter((c) => c.id !== id));
    onDeleted(id);
  };

  const rename = async (id: string, title: string) => {
    const done = await api.renameConversation(id, title).catch(() => null);
    if (done) setData(list.map((c) => (c.id === id ? { ...c, title: done.title } : c)));
  };

  return (
    <>
      {searching && (
        <input className="side-search" autoFocus value={filter} onChange={(e) => onFilter(e.target.value)} placeholder="Buscar chats" aria-label="Buscar chats" />
      )}
      {loading && !data && <div className="skeleton-lines" aria-hidden><span /><span /><span /></div>}
      {data && !shown.length && <p className="side-empty">{needle ? "Ningún chat coincide." : "Tus chats aparecerán aquí."}</p>}
      {groupOrder.map((g) =>
        groups.has(g) ? (
          <section key={g} className="side-group">
            <h3 className="side-label">{g}</h3>
            <ul className="side-list">
              {groups.get(g)!.map((c) => (
                <ConversationRow key={c.id} conv={c} active={c.id === activeId} onSelect={onSelect} onDelete={remove} onRename={rename} />
              ))}
            </ul>
          </section>
        ) : null,
      )}
    </>
  );
}

interface ConvProps {
  conv: ConversationSummary;
  active: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

function ConversationRow({ conv, active, onSelect, onDelete, onRename }: ConvProps) {
  const [menu, setMenu] = useState(false);
  const [editing, setEditing] = useState(false);
  const ref = useOutside<HTMLLIElement>(menu, () => setMenu(false));
  const title = conv.title || "Nueva conversación";

  const commit = (value: string) => {
    setEditing(false);
    const next = value.trim();
    if (next && next !== title) onRename(conv.id, next);
  };

  return (
    <li className="side-item" aria-current={active || undefined} data-menu={menu || undefined} ref={ref}>
      {editing ? (
        <input
          className="side-rename"
          autoFocus
          defaultValue={title}
          onBlur={(e) => commit(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit(e.currentTarget.value);
            if (e.key === "Escape") setEditing(false);
          }}
          aria-label="Nuevo título"
        />
      ) : (
        <button className="side-link" onClick={() => onSelect(conv.id)} title={title}>
          {title}
        </button>
      )}
      <button className="row-more" onClick={() => setMenu((m) => !m)} aria-label="Opciones del chat">
        <MoreHorizontal size={16} />
      </button>
      {menu && (
        <div className="popover row-menu" role="menu">
          <button role="menuitem" onClick={() => (setMenu(false), setEditing(true))}>
            <Pencil size={16} /> Renombrar
          </button>
          <button role="menuitem" className="danger" onClick={() => (setMenu(false), onDelete(conv.id))}>
            <Trash2 size={16} /> Eliminar
          </button>
        </div>
      )}
    </li>
  );
}
