import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { FileUp, GitCompare, ScrollText, Search } from "lucide-react";
import { api, ApiError, streamChat, type Attachment, type Collection, type Source, type UploadFile } from "../api";
import { fromDrop, hasFiles } from "../files";
import { plural } from "../format";
import type { DrawerTarget } from "./DocumentDrawer";
import Answer, { type Turn } from "./Answer";
import Composer, { type PendingFile } from "./Composer";
import FileCard, { extOf } from "./FileCard";
import Dropzone from "./Dropzone";

interface Props {
  collection: Collection;
  conversationId: string | null;
  model: string;
  indexingText: string | null;
  onConversationCreated: (id: string) => void;
  onTitled: () => void;
  onOpenSource: (t: DrawerTarget) => void;
  onFilesAdded: () => void;
  onModelRejected: () => void;
  onChangeFolder: () => void;
}

const suggestions = [
  { icon: ScrollText, text: "Resume los documentos" },
  { icon: Search, text: "Busca un dato concreto" },
  { icon: GitCompare, text: "Compara dos archivos" },
];

export default function ChatView(props: Props) {
  const { collection, conversationId, model, onConversationCreated, onTitled, onOpenSource, onFilesAdded } = props;
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState<PendingFile[]>([]);
  const abort = useRef<AbortController | null>(null);
  // id que acabamos de crear nosotros, para no recargar a mitad del stream
  const ownId = useRef<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  // archivos locales por ruta, para pintar miniaturas sin pedirlas al servidor
  const localFiles = useRef(new Map<string, File>());

  useEffect(() => {
    if (conversationId && conversationId === ownId.current) return;
    abort.current?.abort();
    setLoadError(null);
    if (!conversationId) {
      ownId.current = null;
      setTurns([]);
      return;
    }
    let live = true;
    setLoading(true);
    api
      .conversation(conversationId)
      .then((c) => live && setTurns(c.messages))
      .catch((e: Error) => live && setLoadError(e.message))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [conversationId]);

  useEffect(() => () => abort.current?.abort(), []);

  useEffect(() => {
    const el = scroller.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [turns]);

  const streaming = turns.some((t) => t.streaming);

  const patchLast = (fn: (t: Turn) => Turn) =>
    setTurns((ts) => (ts.length ? [...ts.slice(0, -1), fn(ts[ts.length - 1])] : ts));

  const patchPending = (keys: string[], fn: (f: PendingFile, i: number) => PendingFile) =>
    setPending((ps) => ps.map((p) => (keys.includes(p.key) ? fn(p, keys.indexOf(p.key)) : p)));

  const waitIndexed = async (key: string, path: string) => {
    const name = path.split("/").pop() ?? path;
    for (let i = 0; i < 120; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      const docs = await api.documents(collection.id, name).catch(() => []);
      const doc = docs.find((d) => d.rel_path === path);
      if (doc && (doc.status === "indexed" || doc.status === "error" || doc.status === "skipped")) {
        const failed = doc.status !== "indexed";
        patchPending([key], (f) => ({ ...f, documentId: doc.id, state: failed ? "error" : "ready", error: failed ? doc.error ?? "No se pudo leer" : undefined }));
        return;
      }
    }
    patchPending([key], (f) => ({ ...f, state: "ready" }));
  };

  const attach = async (files: UploadFile[]) => {
    const keys = files.map((f) => `${f.path}-${Math.random().toString(36).slice(2)}`);
    setPending((ps) => [
      ...ps,
      ...files.map((f, i) => ({ key: keys[i], name: f.path, file: f.file, state: "uploading" as const, progress: 0 })),
    ]);
    try {
      const { paths } = await api.addFiles(collection.id, files, (p) => patchPending(keys, (f) => ({ ...f, progress: p })));
      // el servidor devuelve las rutas en el mismo orden en que se enviaron
      const resolved = keys.map((_, i) => paths[i] ?? files[i].path);
      resolved.forEach((p, i) => localFiles.current.set(p, files[i].file));
      patchPending(keys, (f, i) => ({ ...f, progress: 1, state: "indexing", path: resolved[i] }));
      onFilesAdded();
      keys.forEach((k, i) => waitIndexed(k, resolved[i]));
    } catch (e) {
      patchPending(keys, (f) => ({ ...f, state: "error", error: (e as Error).message }));
    }
  };

  const fail = (message: string, status?: number) => {
    const rejected = !!model && (status === 404 || /no existe o no tienes acceso/i.test(message));
    if (rejected) props.onModelRejected();
    patchLast((t) => ({ ...t, error: message, note: rejected ? "Volvimos al modelo automático." : undefined }));
  };

  const send = async (text: string, files?: Attachment[]) => {
    const attachments =
      files ??
      pending
        .filter((p) => p.path)
        .map((p) => ({ id: p.documentId ?? null, rel_path: p.path!, ext: extOf(p.path!), size: p.file.size }));
    if (!files) setPending([]);
    const controller = new AbortController();
    abort.current = controller;
    pinned.current = true;
    const now = Date.now() / 1000;
    setTurns((ts) => [
      ...ts,
      { id: `u-${now}`, role: "user", content: text, sources: null, attachments, created_at: now },
      { id: `a-${now}`, role: "assistant", content: "", sources: null, created_at: now, streaming: true },
    ]);

    try {
      for await (const ev of streamChat(
        {
          collection_id: collection.id,
          conversation_id: conversationId ?? ownId.current ?? undefined,
          message: text,
          model: model || undefined,
          attachments: attachments.length ? attachments.map((a) => a.rel_path) : undefined,
        },
        controller.signal,
      )) {
        if (ev.event === "meta") {
          patchLast((t) => ({ ...t, id: ev.data.message_id }));
          if (ev.data.conversation_id !== conversationId) {
            ownId.current = ev.data.conversation_id;
            onConversationCreated(ev.data.conversation_id);
          }
        } else if (ev.event === "sources") {
          patchLast((t) => ({ ...t, sources: ev.data.sources }));
        } else if (ev.event === "token") {
          patchLast((t) => ({ ...t, content: t.content + ev.data.text }));
        } else if (ev.event === "done") {
          if (ev.data.title) onTitled();
        } else if (ev.event === "error") {
          fail(ev.data.message);
        }
      }
    } catch (e) {
      if (!controller.signal.aborted) fail((e as Error).message, e instanceof ApiError ? e.status : undefined);
    } finally {
      patchLast((t) => ({ ...t, streaming: false }));
    }
  };

  const regenerate = () => {
    const lastUser = [...turns].reverse().find((t) => t.role === "user");
    if (!lastUser) return;
    setTurns((ts) => ts.slice(0, -2));
    send(lastUser.content, lastUser.attachments ?? []);
  };

  const openSource = useCallback(
    (s: Source) => onOpenSource({ documentId: s.document_id, chunkId: s.chunk_id }),
    [onOpenSource],
  );

  const openAttachment = async (a: Attachment) => {
    if (a.id) return onOpenSource({ documentId: a.id });
    const docs = await api.documents(collection.id, a.rel_path).catch(() => []);
    const doc = docs.find((d) => d.rel_path === a.rel_path) ?? docs[0];
    if (doc) onOpenSource({ documentId: doc.id });
  };

  const empty = !loading && !turns.length && !loadError;
  const canAsk = collection.doc_count > 0 || collection.status === "indexing" || pending.length > 0;
  const lastId = turns[turns.length - 1]?.id;

  const indexing = props.indexingText && (
    <div className="indexing-banner">
      <span className="spinner" aria-hidden /> {props.indexingText}
    </div>
  );
  const composer = (
    <Composer
      disabled={!canAsk}
      streaming={streaming}
      attachments={pending}
      onSend={(q) => send(q)}
      onStop={() => abort.current?.abort()}
      onAttach={attach}
      onRemove={(key) => setPending((ps) => ps.filter((p) => p.key !== key))}
      resetKey={conversationId ?? "new"}
    />
  );

  return (
    <div
      className="chat"
      data-empty={empty || undefined}
      onDragOver={(e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
      }}
      onDrop={async (e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        setDragging(false);
        const files = await fromDrop(e.dataTransfer);
        if (files.length) attach(files);
      }}
    >
      <div
        className="chat-scroll"
        ref={scroller}
        onScroll={(e) => {
          const el = e.currentTarget;
          pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
      >
        <div className="thread">
          {loading && <div className="skeleton-lines tall" aria-hidden><span /><span /><span /></div>}
          {loadError && <p className="error-text">{loadError}</p>}
          {empty && (
            <Greeting collection={collection} canAsk={canAsk} onPick={(q) => send(q)} onAttach={attach} onChangeFolder={props.onChangeFolder}>
              {indexing}
              {composer}
            </Greeting>
          )}
          {turns.map((t) =>
            t.role === "user" ? (
              <div key={t.id} className="user-msg">
                {t.attachments && t.attachments.length > 0 && (
                  <div className="user-files">
                    {t.attachments.map((a) => (
                      <FileCard key={a.rel_path} path={a.rel_path} file={localFiles.current.get(a.rel_path)} url={a.id ? api.rawUrl(a.id) : undefined} onOpen={() => openAttachment(a)} />
                    ))}
                  </div>
                )}
                <p>{t.content}</p>
              </div>
            ) : (
              <Answer
                key={t.id}
                turn={t}
                canRegenerate={t.id === lastId && !streaming}
                onOpenSource={openSource}
                onRegenerate={regenerate}
              />
            ),
          )}
        </div>
      </div>

      {!empty && (
        <div className="composer-dock">
          {indexing}
          {composer}
          <p className="composer-note">Folio puede equivocarse. Revisa las fuentes citadas.</p>
        </div>
      )}

      {dragging && (
        <div className="drop-overlay">
          <FileUp size={32} strokeWidth={1.5} />
          <p>Suelta para añadir a «{collection.name}»</p>
        </div>
      )}
    </div>
  );
}

interface GreetingProps {
  collection: Collection;
  canAsk: boolean;
  onPick: (q: string) => void;
  onAttach: (files: UploadFile[]) => void;
  onChangeFolder: () => void;
  children: ReactNode;
}

function Greeting({ collection, canAsk, onPick, onAttach, onChangeFolder, children }: GreetingProps) {
  return (
    <div className="greeting">
      <div className="greeting-head">
        <h1>¿Qué quieres saber de tus documentos?</h1>
        <p className="greeting-folder">
          Preguntando sobre la carpeta <strong>«{collection.name}»</strong> ({plural(collection.doc_count, "documento", "documentos")}) ·{" "}
          <button className="text-link" onClick={onChangeFolder}>Cambiar</button>
        </p>
      </div>
      {children}
      {canAsk ? (
        <>
          <ul className="suggestions">
            {suggestions.map(({ icon: Icon, text }) => (
              <li key={text}>
                <button onClick={() => onPick(text)}>
                  <Icon size={17} /> {text}
                </button>
              </li>
            ))}
          </ul>

        </>
      ) : (
        <Dropzone onFiles={onAttach} compact />
      )}
    </div>
  );
}
