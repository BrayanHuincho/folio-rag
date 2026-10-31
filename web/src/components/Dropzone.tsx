import { useRef, useState } from "react";
import { FileUp } from "lucide-react";
import type { UploadFile } from "../api";
import { fromDrop, fromInput, hasFiles } from "../files";

interface Props {
  onFiles: (files: UploadFile[]) => void;
  disabled?: boolean;
  compact?: boolean;
}

export default function Dropzone({ onFiles, disabled, compact }: Props) {
  const [over, setOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  const take = (files: UploadFile[]) => files.length && onFiles(files);

  return (
    <div
      className="dropzone"
      data-over={over || undefined}
      data-compact={compact || undefined}
      aria-disabled={disabled || undefined}
      onDragOver={(e) => {
        if (disabled || !hasFiles(e)) return;
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={async (e) => {
        if (disabled) return;
        e.preventDefault();
        setOver(false);
        take(await fromDrop(e.dataTransfer));
      }}
    >
      <FileUp size={compact ? 22 : 28} strokeWidth={1.5} className="dropzone-icon" />
      <p className="dropzone-title">Arrastra archivos o carpetas aquí</p>
      <p className="dropzone-sub">PDF, Word, Excel, PowerPoint, texto, Markdown, HTML, EPUB y código</p>
      <div className="dropzone-actions">
        <button type="button" className="btn" disabled={disabled} onClick={() => fileInput.current?.click()}>
          Elegir archivos
        </button>
        <button type="button" className="btn" disabled={disabled} onClick={() => folderInput.current?.click()}>
          Elegir carpeta
        </button>
      </div>
      <input
        ref={fileInput}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          take(fromInput(e.target.files));
          e.target.value = "";
        }}
      />
      <input
        ref={folderInput}
        type="file"
        hidden
        {...{ webkitdirectory: "", directory: "" }}
        onChange={(e) => {
          take(fromInput(e.target.files));
          e.target.value = "";
        }}
      />
    </div>
  );
}
