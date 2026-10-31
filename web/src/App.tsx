import { useCallback, useEffect, useState } from "react";
import { PanelLeftOpen, SquarePen } from "lucide-react";
import { api, type Collection, type UploadFile } from "./api";
import { useAsync, useCollectionProgress, useHotkey, useStoredState } from "./hooks";
import { useToast } from "./toast";
import Sidebar from "./components/Sidebar";
import ChatView from "./components/ChatView";
import DocumentsView from "./components/DocumentsView";
import DocumentDrawer, { type DrawerTarget } from "./components/DocumentDrawer";
import NewCollectionDialog, { type Mode } from "./components/NewCollectionDialog";
import ModelMenu from "./components/ModelMenu";
import FolderMenu from "./components/FolderMenu";
import Onboarding from "./components/Onboarding";

type Tab = "chat" | "documents";

export default function App() {
  const toast = useToast();
  const collections = useAsync(api.collections, []);
  const [collectionId, setCollectionId] = useStoredState<string>("folio.collection", "");
  const [model, setModel] = useStoredState<string>("folio.model.v2", "");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("chat");
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);
  const [dialog, setDialog] = useState<Mode | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [resolvedModel, setResolvedModel] = useState("");
  const [folderMenu, setFolderMenu] = useState(false);
  const [convVersion, setConvVersion] = useState(0);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  // tras subir archivos escuchamos el SSE aunque el estado aún no diga indexing
  const [watching, setWatching] = useState(false);

  const list = collections.data ?? [];
  const current: Collection | undefined = list.find((c) => c.id === collectionId) ?? list[0];

  useEffect(() => {
    if (current && current.id !== collectionId) setCollectionId(current.id);
  }, [current, collectionId, setCollectionId]);

  const reload = collections.reload;
  const progress = useCollectionProgress(current?.id ?? "", !!current && (current.status === "indexing" || watching), () => {
    setWatching(false);
    reload();
  });

  const newChat = useCallback(() => {
    setConversationId(null);
    setTab("chat");
    setSidebarOpen(false);
  }, []);

  useHotkey((e) => (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k", newChat);

  const selectCollection = (id: string) => {
    setCollectionId(id);
    setConversationId(null);
    setSidebarOpen(false);
  };

  const created = (c: Collection) => {
    setDialog(null);
    collections.setData([...list.filter((x) => x.id !== c.id), c]);
    selectCollection(c.id);
    setTab("chat");
    setWatching(true);

  };

  const attach = async (files: UploadFile[]) => {
    if (!current || uploadPct !== null) return;
    setUploadPct(0);
    try {
      await api.addFiles(current.id, files, setUploadPct);
      setWatching(true);
      reload();
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setUploadPct(null);
    }
  };

  const indexingText =
    uploadPct !== null
      ? `Subiendo archivos… ${Math.round(uploadPct * 100)} %`
      : progress?.state === "indexing"
        ? progress.total
          ? `Indexando ${progress.done} de ${progress.total} documentos…`
          : "Revisando la carpeta…"
        : null;

  return (
    <div className="shell" data-sidebar-open={sidebarOpen || undefined} data-collapsed={collapsed || undefined}>
      <Sidebar
        documentsActive={tab === "documents"}
        modelName={resolvedModel}
        onDocuments={() => {
          setTab("documents");
          setSidebarOpen(false);
        }}
        collections={list}
        current={current}
        progressText={progress?.state === "indexing" && progress.total ? `Indexando ${progress.done}/${progress.total}` : null}
        conversationId={conversationId}
        convVersion={convVersion}
        onSelectCollection={selectCollection}
        onSelectConversation={(id) => {
          setConversationId(id);
          setTab("chat");
          setSidebarOpen(false);
        }}
        onConversationDeleted={(id) => id === conversationId && setConversationId(null)}
        onNewChat={newChat}
        onNewCollection={() => setDialog("upload")}
        onChanged={reload}
        onClose={() => {
          setSidebarOpen(false);
          if (matchMedia("(min-width: 861px)").matches) setCollapsed(true);
        }}
      />
      <div className="scrim" onClick={() => setSidebarOpen(false)} />

      <main className="main">
        <header className="topbar">
          <button
            className="icon-btn sidebar-open"
            onClick={() => {
              setSidebarOpen(true);
              setCollapsed(false);
            }}
            aria-label="Abrir barra lateral"
            title="Abrir barra lateral"
          >
            <PanelLeftOpen size={18} />
          </button>
          {current && <ModelMenu value={model} onChange={setModel} onResolved={setResolvedModel} />}
          {list.length > 0 && (
            <FolderMenu
              collections={list}
              current={current}
              progressText={progress?.state === "indexing" && progress.total ? `indexando ${progress.done}/${progress.total}` : null}
              open={folderMenu}
              onOpenChange={setFolderMenu}
              onSelect={selectCollection}
              onAdd={() => setDialog("upload")}
            />
          )}
          {current && tab === "chat" && (
            <button className="icon-btn topbar-new" onClick={newChat} aria-label="Chat nuevo" title="Chat nuevo">
              <SquarePen size={18} />
            </button>
          )}
        </header>

        {current ? (
          tab === "chat" ? (
            <ChatView
              key={current.id}
              collection={current}
              conversationId={conversationId}
              model={model}
              indexingText={indexingText}
              onConversationCreated={(id) => {
                setConversationId(id);
                setConvVersion((v) => v + 1);
              }}
              onTitled={() => setConvVersion((v) => v + 1)}
              onOpenSource={setDrawer}
              onModelRejected={() => setModel("")}
              onChangeFolder={() => setFolderMenu(true)}
              onFilesAdded={() => {
                setWatching(true);
                reload();
              }}
            />
          ) : (
            <DocumentsView key={current.id} collection={current} onOpen={(id) => setDrawer({ documentId: id })} onAttach={attach} />
          )
        ) : collections.loading ? null : collections.error ? (
          <ServerDown error={collections.error} onRetry={reload} />
        ) : (
          <Onboarding onUpload={() => setDialog("upload")} onUseFolder={() => setDialog("folder")} />
        )}
      </main>

      {drawer && <DocumentDrawer target={drawer} onClose={() => setDrawer(null)} />}
      {dialog && <NewCollectionDialog initialMode={dialog} onClose={() => setDialog(null)} onCreated={created} />}
    </div>
  );
}

function ServerDown({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="center-state">
      <h1>No se puede conectar con Folio</h1>
      <p>
        {error}. Inicia el servidor con <code>python -m folio</code> y vuelve a intentarlo.
      </p>
      <button className="btn" onClick={onRetry}>Reintentar</button>
    </div>
  );
}


