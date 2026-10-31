import { KeyRound, TriangleAlert } from "lucide-react";
import { isApiKeyError } from "../api";

function split(message: string): { summary: string; detail: string | null } {
  const idx = message.indexOf("\n\nDetalle:");
  if (idx === -1) return { summary: message, detail: null };
  return { summary: message.slice(0, idx), detail: message.slice(idx + 10).trim() };
}

export default function ErrorNotice({ message }: { message: string }) {
  const { summary, detail } = split(message);
  const keyMissing = isApiKeyError(summary);

  return (
    <div className="notice" data-kind={keyMissing ? "key" : undefined}>
      {keyMissing ? <KeyRound size={18} /> : <TriangleAlert size={18} />}
      <div className="grow">
        <strong>{keyMissing ? "Falta una clave de API" : "No se pudo completar la respuesta"}</strong>
        <p>{summary}</p>
        {keyMissing && (
          <ol>
            <li>Abre el archivo <code>.env</code> en la carpeta de Folio (copia <code>.env.example</code> si no existe).</li>
            <li>Pega tu clave en la variable del proveedor, por ejemplo <code>OPENROUTER_API_KEY=sk-...</code></li>
            <li>Reinicia el servidor con <code>python -m folio</code> y vuelve a preguntar.</li>
          </ol>
        )}
        {detail && (
          <details>
            <summary>Ver detalle técnico</summary>
            <pre>{detail}</pre>
          </details>
        )}
      </div>
    </div>
  );
}
