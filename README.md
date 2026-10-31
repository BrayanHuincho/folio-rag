# Folio

Apunta Folio a una carpeta y pregúntale lo que quieras sobre lo que hay dentro. Lee PDFs, Word, Excel, presentaciones, código, correos, notebooks y casi cualquier texto, y cada respuesta te dice de qué archivo y de qué página salió.

Lo armé porque estaba cansado de abrir veinte PDFs para encontrar un párrafo. La idea es simple: tus archivos se quedan en tu máquina, el índice también, y tú eliges qué modelo responde.

## Qué hace bien

- **Búsqueda híbrida.** Combina búsqueda semántica (embeddings) con búsqueda por palabras exactas (BM25) y las fusiona. Así encuentra "penalidad por retraso" aunque el documento diga "multa por demora", y también encuentra un número de contrato exacto.
- **Citas de verdad.** Cada respuesta numera sus fuentes. Haces clic en `[2]` y ves el fragmento original resaltado.
- **Se mantiene al día solo.** Vigila la carpeta: si agregas, editas o borras un archivo, reindexa solo eso.
- **Cualquier modelo.** OpenRouter, OpenAI, Anthropic, Gemini, Groq, Mistral, DeepSeek, Ollama o LM Studio. Cambias de modelo desde la misma conversación.
- **Embeddings locales.** Por defecto los vectores se calculan en tu CPU con un modelo multilingüe. No se manda ningún archivo a ninguna API para indexar.
- **Conversaciones con memoria.** Las preguntas de seguimiento ("¿y el de 45 kg?") se reescriben con el contexto antes de buscar.

## Formatos

PDF · DOCX · ODT · RTF · XLSX · ODS · CSV/TSV · PPTX · HTML · EPUB · Markdown · TXT · JSON/JSONL · YAML · TOML · XML · INI · IPYNB · EML · código fuente de los lenguajes comunes · imágenes (con `FOLIO_OCR=true` y un modelo con visión).

Ignora `.git`, `node_modules`, `.venv` y similares. Si quieres excluir algo más, crea un `.folioignore` en la carpeta con patrones al estilo `.gitignore`.

## Cómo correrlo

Necesitas Python 3.11+ y Node 20+ con pnpm.

```bash
cp .env.example .env        # y pon tu key, por ejemplo OPENROUTER_API_KEY

cd backend
python -m venv .venv
.venv/Scripts/activate      # en Linux/macOS: source .venv/bin/activate
pip install -e .

cd ../web
pnpm install
pnpm build

cd ../backend
python -m folio
```

Abre http://127.0.0.1:8765, agrega una carpeta y pregunta. La primera vez descarga el modelo de embeddings (unos 200 MB), así que tarda un poco.

Para trabajar en el frontend: `pnpm dev` en `web/` y abre http://localhost:5173 (las llamadas a `/api` van al backend).

### Sin internet

Con Ollama todo queda en tu máquina:

```env
FOLIO_LLM=ollama:llama3.1
FOLIO_EMBEDDINGS=local:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

## Configuración

Todo vive en `.env`, en la raíz del repo. `.env.example` tiene cada variable. Las que más vas a tocar:

| Variable | Para qué |
|---|---|
| `FOLIO_LLM` | Modelo por defecto, `proveedor:modelo` |
| `FOLIO_FAST_LLM` | Modelo barato para reescribir preguntas y poner títulos (opcional) |
| `FOLIO_EMBEDDINGS` | `local:...`, `openai:text-embedding-3-small`, `ollama:nomic-embed-text`... |
| `FOLIO_TOP_K` | Cuántos fragmentos se le pasan al modelo |
| `FOLIO_CHUNK_SIZE` | Tamaño aproximado de cada fragmento, en tokens |

Si cambias de modelo de embeddings, reindexa la carpeta: los vectores de modelos distintos no se pueden comparar.

## Cómo está hecho

```
backend/folio
  ingest/   parsers por familia de archivo, chunker que respeta títulos y párrafos, pipeline incremental y watcher
  embed/    embeddings locales (fastembed/ONNX) o remotos
  index/    SQLite: FTS5 para texto, vectores en el mismo archivo, búsqueda híbrida con RRF + MMR
  llm/      un cliente compatible con OpenAI para casi todos, y uno nativo para Anthropic
  rag/      reescritura de la pregunta, recuperación, prompt con fuentes y streaming
  api/      FastAPI + SSE
web/        React + TypeScript + Vite, sin librerías de UI
```

Todo cabe en un solo archivo `data/folio.db`. No hay que levantar Postgres, Qdrant ni nada aparte. Para carpetas de hasta unos cientos de miles de fragmentos la búsqueda en memoria con numpy va de sobra.

## Tests

```bash
cd backend
python -m pytest
```

## Licencia

MIT
