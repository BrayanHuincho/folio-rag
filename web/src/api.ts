export type CollectionStatus = "idle" | "indexing" | "error";

export interface Progress {
  state: string;
  done: number;
  total: number;
  current: string | null;
  errors?: number;
}

export interface Collection {
  id: string;
  name: string;
  path: string;
  status: CollectionStatus;
  error: string | null;
  doc_count: number;
  chunk_count: number;
  size_bytes: number;
  created_at: number;
  updated_at: number;
  progress: Progress | null;
  managed: boolean;
}

export interface UploadFile {
  file: File;
  path: string;
}

export type DocumentStatus = "pending" | "indexed" | "skipped" | "error";

export interface DocumentRow {
  id: string;
  rel_path: string;
  ext: string;
  size: number;
  status: DocumentStatus;
  error: string | null;
  chunk_count: number;
  indexed_at: number | null;
}

export interface Chunk {
  id: string;
  ord: number;
  page: number | null;
  heading: string | null;
  text: string;
}

export interface DocumentDetail extends DocumentRow {
  chunks: Chunk[];
}

export interface TablePreview {
  sheets: { name: string; rows: string[][]; truncated: boolean }[];
  max_rows: number;
}

export interface BrowseResult {
  path: string;
  parent: string | null;
  dirs: { name: string; path: string }[];
}

export interface ModelInfo {
  id: string;
  name: string;
  free?: boolean;
  price_in?: number | null;
  price_out?: number | null;
}

export interface ModelProvider {
  id: string;
  configured: boolean;
  models: ModelInfo[];
}

export interface ModelsResponse {
  default: string;
  pinned?: boolean;
  providers: ModelProvider[];
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  model: string | null;
  updated_at: number;
}

export interface Source {
  n: number;
  chunk_id: string;
  document_id: string;
  rel_path: string;
  page: number | null;
  heading: string | null;
  snippet: string;
  score: number;
}

export interface Attachment {
  id: string | null;
  rel_path: string;
  ext: string;
  size: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[] | null;
  attachments?: Attachment[];
  created_at: number;
}

export interface Conversation {
  id: string;
  title: string | null;
  model: string | null;
  messages: Message[];
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  if (res.status === 204 || res.status === 202) return undefined as T;
  return res.json() as Promise<T>;
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  } catch {
    // el cuerpo no era JSON, usamos el statusText
  }
  return res.statusText || `La petición falló (${res.status})`;
}

function detailFrom(text: string, status: number): string {
  try {
    const detail = JSON.parse(text)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  } catch {
    // respuesta no JSON
  }
  return status ? `La subida falló (${status})` : "No se pudo conectar con el servidor";
}

// fetch no expone el progreso de subida, por eso XHR
function upload<T>(url: string, form: FormData, onProgress?: (fraction: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve(JSON.parse(xhr.responseText || "null") as T)
        : reject(new ApiError(xhr.status, detailFrom(xhr.responseText, xhr.status)));
    xhr.onerror = () => reject(new ApiError(0, detailFrom("", 0)));
    xhr.send(form);
  });
}

function filesForm(files: UploadFile[], name?: string): FormData {
  const form = new FormData();
  if (name) form.append("name", name);
  for (const f of files) form.append("files", f.file, f.path);
  return form;
}

export function isApiKeyError(message: string): boolean {
  return /api[\s_-]?key|clave de api|clave api/i.test(message);
}

const q = (params: Record<string, string | undefined>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) s.set(k, v);
  const str = s.toString();
  return str ? `?${str}` : "";
};

export const api = {
  collections: () => request<Collection[]>("/collections"),
  createCollection: (name: string, path: string) =>
    request<Collection>("/collections", { method: "POST", body: JSON.stringify({ name, path }) }),
  deleteCollection: (id: string) => request<void>(`/collections/${id}`, { method: "DELETE" }),
  reindex: (id: string, full = false) =>
    request<void>(`/collections/${id}/reindex${q({ full: String(full) })}`, { method: "POST" }),
  documents: (collectionId: string, search?: string) =>
    request<DocumentRow[]>(`/collections/${collectionId}/documents${q({ q: search || undefined })}`),
  document: (id: string) => request<DocumentDetail>(`/documents/${id}`),
  rawUrl: (id: string) => `/api/documents/${id}/raw`,
  table: (id: string) => request<TablePreview>(`/documents/${id}/table`),
  rawText: async (id: string) => {
    const res = await fetch(`/api/documents/${id}/raw`);
    if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
    return res.text();
  },
  rawBlob: async (id: string) => {
    const res = await fetch(`/api/documents/${id}/raw`);
    if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
    return res.blob();
  },
  browse: (path = "") => request<BrowseResult>(`/fs/browse${q({ path })}`),
  models: () => request<ModelsResponse>("/models"),
  conversations: (collectionId: string) =>
    request<ConversationSummary[]>(`/conversations${q({ collection_id: collectionId })}`),
  conversation: (id: string) => request<Conversation>(`/conversations/${id}`),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
  renameConversation: (id: string, title: string) =>
    request<{ id: string; title: string }>(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  eventsUrl: (collectionId: string) => `/api/collections/${collectionId}/events`,
  uploadCollection: (files: UploadFile[], name?: string, onProgress?: (f: number) => void) =>
    upload<Collection>("/api/collections/upload", filesForm(files, name), onProgress),
  addFiles: (collectionId: string, files: UploadFile[], onProgress?: (f: number) => void) =>
    upload<{ saved: number; paths: string[] }>(`/api/collections/${collectionId}/files`, filesForm(files), onProgress),
};

export interface ChatRequest {
  collection_id: string;
  conversation_id?: string;
  message: string;
  model?: string;
  top_k?: number;
  attachments?: string[];
}

export type ChatEvent =
  | { event: "meta"; data: { conversation_id: string; message_id: string; model: string } }
  | { event: "sources"; data: { sources: Source[] } }
  | { event: "token"; data: { text: string } }
  | { event: "done"; data: { usage?: unknown; title?: string } }
  | { event: "error"; data: { message: string } };

// EventSource no soporta POST, así que parseamos el SSE a mano
export async function* streamChat(body: ChatRequest, signal: AbortSignal): AsyncGenerator<ChatEvent> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, await errorMessage(res));

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n/g, "\n");
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const parsed = parseFrame(frame);
      if (parsed) yield parsed;
    }
  }
}

function parseFrame(frame: string): ChatEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith(":")) continue;
    const idx = line.indexOf(":");
    const field = idx === -1 ? line : line.slice(0, idx);
    const value = idx === -1 ? "" : line.slice(idx + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) } as ChatEvent;
  } catch {
    return null;
  }
}
