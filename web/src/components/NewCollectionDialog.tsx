import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import type { Collection } from "../api";
import UploadForm from "./UploadForm";
import FolderForm from "./FolderForm";

export type Mode = "upload" | "folder";

interface Props {
  initialMode?: Mode;
  onClose: () => void;
  onCreated: (c: Collection) => void;
}

export default function NewCollectionDialog({ initialMode = "upload", onClose, onCreated }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [mode, setMode] = useState<Mode>(initialMode);

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  return (
    <dialog ref={dialog} className="dialog" onClose={onClose} onCancel={onClose}>
      <header className="dialog-head">
        <h2>Agregar carpeta</h2>
        <button className="icon-btn" onClick={onClose} aria-label="Cerrar">
          <X size={18} />
        </button>
      </header>
      <div className="segmented" role="tablist">
        <button role="tab" aria-selected={mode === "upload"} onClick={() => setMode("upload")}>Subir archivos</button>
        <button role="tab" aria-selected={mode === "folder"} onClick={() => setMode("folder")}>Carpeta del equipo</button>
      </div>
      <div className="dialog-body">
        {mode === "upload" ? (
          <UploadForm onCreated={onCreated} onCancel={onClose} />
        ) : (
          <FolderForm onCreated={onCreated} onCancel={onClose} />
        )}
      </div>
    </dialog>
  );
}
