import { FolderOpen, Upload } from "lucide-react";

const steps = [
  { title: "Agrega una carpeta o sube archivos", text: "PDF, Word, Excel, PowerPoint, texto, código y más." },
  { title: "Espera a que se indexen", text: "Folio lee cada archivo en tu equipo. Suele tardar unos segundos." },
  { title: "Pregunta", text: "Cada respuesta cita el pasaje exacto del documento de donde sale." },
];

export default function Onboarding({ onUpload, onUseFolder }: { onUpload: () => void; onUseFolder: () => void }) {
  return (
    <div className="onboarding">
      <div className="onboarding-inner">
        <span className="brand-mark" aria-hidden>F</span>
        <h1>Conversa con tus documentos</h1>
        <p className="onboarding-sub">Para empezar, dile a Folio qué documentos debe leer.</p>
        <ol className="steps">
          {steps.map((s) => (
            <li key={s.title}>
              <strong>{s.title}</strong>
              <span>{s.text}</span>
            </li>
          ))}
        </ol>
        <div className="onboarding-actions">
          <button className="btn btn-primary btn-large" onClick={onUpload}>
            <Upload size={18} /> Subir archivos
          </button>
          <button className="btn btn-large" onClick={onUseFolder}>
            <FolderOpen size={18} /> Elegir carpeta del equipo
          </button>
        </div>
      </div>
    </div>
  );
}
