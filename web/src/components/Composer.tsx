import { useEffect, useRef, useState } from "react";
import { ArrowUp, Plus, Square } from "lucide-react";
import type { UploadFile } from "../api";
import { fromInput } from "../files";
import FileCard, { type FileState } from "./FileCard";

export interface PendingFile {
  key: string;
  name: string;
  file: File;
  state: FileState;
  progress: number;
  path?: string;
  documentId?: string;
  error?: string;
}

interface Props {
  disabled: boolean;
  streaming: boolean;
  attachments: PendingFile[];
  onSend: (text: string) => void;
  onStop: () => void;
  onAttach: (files: UploadFile[]) => void;
  onRemove: (key: string) => void;
  resetKey: string;
}

export default function Composer(props: Props) {
  const { disabled, streaming, attachments, onSend, onStop, onAttach, onRemove, resetKey } = props;
  const [text, setText] = useState("");
  const area = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);

  useEffect(() => {
    area.current?.focus();
  }, [resetKey]);

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const uploading = attachments.some((f) => f.state === "uploading");
  const canSend = !!text.trim() && !disabled && !streaming && !uploading;

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <div className="composer" data-tall={attachments.length > 0 || text.includes("\n") || text.length > 70 || undefined}>
      {attachments.length > 0 && (
        <div className="composer-files">
          {attachments.map((f) => (
            <FileCard
              key={f.key}
              path={f.name}
              file={f.file}
              state={f.state}
              progress={f.progress}
              error={f.error}
              onRemove={() => onRemove(f.key)}
            />
          ))}
        </div>
      )}
      <div className="composer-row">
        <button className="composer-attach" onClick={() => picker.current?.click()} title="Adjuntar archivos" aria-label="Adjuntar archivos">
          <Plus size={20} />
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
        <textarea
          ref={area}
          rows={1}
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={
            disabled
              ? "Esperando a que se indexen los documentos…"
              : attachments.length
                ? "Pregunta sobre el archivo"
                : "Pregunta sobre tus documentos"
          }
          aria-label="Tu pregunta"
        />
        {streaming ? (
          <button className="send" onClick={onStop} aria-label="Detener respuesta" title="Detener">
            <Square size={12} fill="currentColor" />
          </button>
        ) : (
          <button className="send" onClick={submit} disabled={!canSend} aria-label="Enviar" title={uploading ? "Esperando a que termine la subida" : "Enviar (Enter)"}>
            <ArrowUp size={18} strokeWidth={2.5} />
          </button>
        )}
      </div>
    </div>
  );
}
