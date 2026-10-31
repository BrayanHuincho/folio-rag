import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Sparkles } from "lucide-react";
import { api, type ModelProvider } from "../api";
import { useAsync } from "../hooks";

const providerNames: Record<string, string> = {
  openrouter: "OpenRouter",
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Google Gemini",
  groq: "Groq",
  mistral: "Mistral",
  deepseek: "DeepSeek",
  ollama: "Ollama",
  lmstudio: "LM Studio",
};

const recommended = [
  "anthropic/claude-sonnet-4.5",
  "anthropic/claude-haiku-4.5",
  "openai/gpt-5",
  "openai/gpt-5-mini",
  "openai/gpt-4.1-mini",
  "google/gemini-2.5-pro",
  "google/gemini-2.5-flash",
  "deepseek/deepseek-chat",
  "meta-llama/llama-3.3-70b-instruct",
];

type Chip = "all" | "free" | "cheap";

const chips: { id: Chip; label: string }[] = [
  { id: "all", label: "Todos" },
  { id: "free", label: "Gratis" },
  { id: "cheap", label: "Baratos (<$1)" },
];

export const providerName = (id: string) => providerNames[id] ?? id;

export function shortName(spec: string): string {
  const model = spec.slice(spec.indexOf(":") + 1);
  return (model.split("/").pop() || model).replace(/:free$/, "");
}

interface Option {
  id: string;
  name: string;
  provider: string;
  free: boolean;
  priceIn: number | null;
  priceOut: number | null;
}

function optionsOf(providers: ModelProvider[]): Option[] {
  return providers.flatMap((p) =>
    p.models.map((m) => ({
      id: m.id,
      name: m.name || shortName(m.id),
      provider: p.id,
      free: !!m.free,
      priceIn: m.price_in ?? null,
      priceOut: m.price_out ?? null,
    })),
  );
}

function money(n: number): string {
  const digits = n >= 10 ? 0 : n >= 1 ? 1 : 2;
  return `$${Number(n.toFixed(digits))}`;
}

const isCheap = (o: Option) => o.free || (o.priceIn !== null && o.priceIn < 1 && (o.priceOut ?? 0) < 1);

// "openrouter:anthropic/claude-sonnet-4.5" y "anthropic:claude-sonnet-4.5" cuentan como el mismo recomendado
function matchesRecommended(id: string, wanted: string): boolean {
  const model = id.slice(id.indexOf(":") + 1);
  const short = wanted.split("/").pop()!;
  return model === wanted || model === short || model.endsWith(`/${short}`);
}

interface Props {
  value: string;
  onChange: (m: string) => void;
  onResolved?: (label: string) => void;
}

export default function ModelMenu({ value, onChange, onResolved }: Props) {
  const { data, error } = useAsync(api.models, []);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [chip, setChip] = useState<Chip>("all");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const providers = data?.providers.filter((p) => p.configured && p.models.length) ?? [];
  const all = optionsOf(providers);
  const selected = all.find((o) => o.id === value);
  const known = !value || !!selected;

  useEffect(() => {
    if (data && !known) onChange("");
  }, [data, known, onChange]);

  const autoLabel = data ? shortName(data.default) : "";

  useEffect(() => {
    if (data) onResolved?.(selected ? shortName(selected.id) : `Automático (${autoLabel})`);
  }, [data, selected, autoLabel, onResolved]);

  const pick = (id: string) => {
    onChange(id);
    setOpen(false);
    setFilter("");
    setChip("all");
  };

  const needle = filter.trim().toLowerCase();
  const pinned = !!data?.pinned;
  const searchable = !pinned && all.length > 8;
  const narrowed = all.filter(
    (o) =>
      (!needle || `${o.id} ${o.name}`.toLowerCase().includes(needle)) &&
      (chip === "all" || (chip === "free" ? o.free : isCheap(o))),
  );
  const browsing = !needle && chip === "all" && !pinned;
  const free = browsing ? all.filter((o) => o.free) : [];
  const picks = browsing
    ? recommended.map((r) => all.find((o) => matchesRecommended(o.id, r))).filter((o): o is Option => !!o)
    : [];

  const row = (o: Option, prefix = "") => <ModelOption key={prefix + o.id} option={o} selected={value === o.id} onPick={pick} />;

  return (
    <div className="model-menu" ref={ref}>
      <button className="model-trigger" onClick={() => setOpen((o) => !o)} aria-expanded={open} disabled={!data} title={error ?? undefined}>
        <span>
          Folio <em>{error ? "Modelos no disponibles" : !data ? "Cargando…" : selected ? shortName(selected.id) : "Automático"}</em>
        </span>
        {selected?.free && <span className="free-badge">Gratis</span>}
        <ChevronDown size={16} />
      </button>
      {open && data && (
        <div className="popover model-list" role="listbox">
          {searchable && (
            <div className="model-tools">
              <input
                className="model-filter"
                autoFocus
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Buscar modelo"
                aria-label="Buscar modelo"
              />
              <div className="chips" role="radiogroup" aria-label="Filtrar modelos">
                {chips.map((c) => (
                  <button key={c.id} role="radio" aria-checked={chip === c.id} onClick={() => setChip(c.id)}>
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
          )}
          {!needle && chip === "all" && (
            <button role="option" aria-selected={!value} onClick={() => pick("")} className="model-option">
              <Sparkles size={16} />
              <span className="grow">
                Automático
                <small>Usa el modelo del .env · {autoLabel}</small>
              </span>
              {!value && <Check size={16} />}
            </button>
          )}
          {free.length > 0 && (
            <>
              <div className="popover-label">Gratis</div>
              {free.map((o) => row(o, "f-"))}
            </>
          )}
          {picks.length > 0 && (
            <>
              <div className="popover-label">Recomendados</div>
              {picks.map((o) => row(o, "r-"))}
            </>
          )}
          {browsing && (free.length > 0 || picks.length > 0) && <div className="popover-label strong">Todos</div>}
          {providers.map((p) => {
            const items = narrowed.filter((o) => o.provider === p.id);
            if (!items.length) return null;
            return (
              <div key={p.id}>
                <div className="popover-label">{providerName(p.id)}</div>
                {items.map((o) => row(o))}
              </div>
            );
          })}
          {(needle || chip !== "all") && !narrowed.length && <p className="popover-empty">Ningún modelo coincide.</p>}
          {!providers.length && <p className="popover-empty">No hay proveedores configurados. Añade una clave de API en .env.</p>}
        </div>
      )}
    </div>
  );
}

function ModelOption({ option, selected, onPick }: { option: Option; selected: boolean; onPick: (id: string) => void }) {
  const price =
    !option.free && option.priceIn !== null && option.priceOut !== null ? `${money(option.priceIn)} / ${money(option.priceOut)}` : null;
  return (
    <button role="option" aria-selected={selected} onClick={() => onPick(option.id)} title={option.id} className="model-option">
      <span className="grow">
        <span className="ellipsis block">{option.name}</span>
        <small className="model-provider">{providerName(option.provider)}</small>
      </span>
      {option.free && <span className="free-badge">Gratis</span>}
      {price && (
        <span className="model-price" title="Entrada / salida por millón de tokens">
          {price}
        </span>
      )}
      {selected && <Check size={16} />}
    </button>
  );
}
