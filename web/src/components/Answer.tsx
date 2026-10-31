import { memo, useMemo, useState, type ReactNode } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, ChevronDown, Copy, FileText, RotateCcw } from "lucide-react";
import type { Message, Source } from "../api";
import { basename, dirname, plural } from "../format";
import ErrorNotice from "./ErrorNotice";

export interface Turn extends Message {
  streaming?: boolean;
  error?: string;
  note?: string;
}

interface Props {
  turn: Turn;
  canRegenerate: boolean;
  onOpenSource: (s: Source) => void;
  onRegenerate: () => void;
}

// [1] o [1, 3] pasan a links #cite-n que luego se pintan como chips
function linkCitations(text: string): string {
  return text.replace(/\[(\d+(?:\s*,\s*\d+)*)\](?!\()/g, (_, nums: string) =>
    nums
      .split(",")
      .map((n) => `[${n.trim()}](#cite-${n.trim()})`)
      .join(""),
  );
}

function useCopy() {
  const [copied, setCopied] = useState(false);
  const copy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return [copied, copy] as const;
}

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (node && typeof node === "object" && "props" in node) return textOf((node.props as { children?: ReactNode }).children);
  return "";
}

function CodeBlock({ children }: { children?: ReactNode }) {
  const [copied, copy] = useCopy();
  const child = Array.isArray(children) ? children[0] : children;
  const className = (child as { props?: { className?: string } })?.props?.className ?? "";
  const lang = className.replace("language-", "");
  return (
    <div className="code-block">
      <div className="code-head">
        <span>{lang || "código"}</span>
        <button onClick={() => copy(textOf(children).replace(/\n$/, ""))}>
          {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
}

function Answer({ turn, canRegenerate, onOpenSource, onRegenerate }: Props) {
  const [copied, copy] = useCopy();
  const [activeN, setActiveN] = useState<number | null>(null);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const sources = turn.sources ?? [];

  const components = useMemo<Components>(
    () => ({
      pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
      table: ({ children }) => (
        <div className="table-scroll">
          <table>{children}</table>
        </div>
      ),
      a({ href, children }) {
        const m = href?.match(/^#cite-(\d+)$/);
        if (!m) return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
        const n = Number(m[1]);
        const source = sources.find((s) => s.n === n);
        return (
          <button
            className="cite"
            disabled={!source}
            title={source ? basename(source.rel_path) : undefined}
            onClick={() => {
              if (!source) return;
              setActiveN(n);
              setSourcesOpen(true);
              onOpenSource(source);
            }}
            aria-label={`Fuente ${n}`}
          >
            {n}
          </button>
        );
      },
    }),
    [sources, onOpenSource],
  );

  const waiting = turn.streaming && !turn.content;
  const files = new Set(sources.map((s) => s.document_id)).size;

  return (
    <article className="answer" aria-busy={turn.streaming || undefined}>
      <div className="answer-body">
        {waiting && (
          <p className="thinking">
            <span className="dots" aria-hidden><i /><i /><i /></span>
            {turn.sources ? "Redactando la respuesta" : "Buscando en tus documentos"}
          </p>
        )}
        {turn.content && (
          <div className="prose" data-streaming={turn.streaming || undefined}>
            <Markdown remarkPlugins={[remarkGfm]} components={components}>
              {linkCitations(turn.content)}
            </Markdown>
          </div>
        )}
        {turn.error && <ErrorNotice message={turn.error} />}
        {turn.note && <p className="answer-note">{turn.note}</p>}
        {!turn.streaming && !turn.content && !turn.error && <p className="muted">Respuesta detenida.</p>}

        {!turn.streaming && (sources.length > 0 || turn.content) && (
          <div className="answer-tools">
            {sources.length > 0 && !turn.error && (
              <button className="sources-pill" onClick={() => setSourcesOpen((o) => !o)} aria-expanded={sourcesOpen}>
                <FileText size={14} />
                {plural(sources.length, "fuente", "fuentes")}
                {files !== sources.length && <span className="muted"> de {plural(files, "archivo", "archivos")}</span>}
                <ChevronDown size={14} className="chev" />
              </button>
            )}
            {turn.content && (
              <span className="answer-actions">
                <button className="icon-btn" onClick={() => copy(turn.content)} title="Copiar" aria-label="Copiar respuesta">
                  {copied ? <Check size={15} /> : <Copy size={15} />}
                </button>
                {canRegenerate && (
                  <button className="icon-btn" onClick={onRegenerate} title="Regenerar" aria-label="Regenerar respuesta">
                    <RotateCcw size={15} />
                  </button>
                )}
              </span>
            )}
          </div>
        )}

        {sourcesOpen && sources.length > 0 && (
          <ol className="source-cards">
            {sources.map((s) => (
              <li key={s.chunk_id}>
                <button
                  className="source-card"
                  data-active={s.n === activeN || undefined}
                  onClick={() => {
                    setActiveN(s.n);
                    onOpenSource(s);
                  }}
                >
                  <span className="source-head">
                    <span className="source-n">{s.n}</span>
                    <span className="source-file">{basename(s.rel_path)}</span>
                  </span>
                  <span className="source-loc">
                    {[dirname(s.rel_path), s.page !== null ? `pág. ${s.page}` : null, s.heading].filter(Boolean).join(" / ")}
                  </span>
                  <span className="source-snippet">{s.snippet}</span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </article>
  );
}

export default memo(Answer);
