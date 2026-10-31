import type { UploadFile } from "./api";

export function fromInput(list: FileList | null): UploadFile[] {
  return Array.from(list ?? []).map((file) => ({ file, path: file.webkitRelativePath || file.name }));
}

export function hasFiles(e: React.DragEvent): boolean {
  return Array.from(e.dataTransfer.types).includes("Files");
}

// las carpetas soltadas solo se pueden recorrer con la API de entries
export async function fromDrop(data: DataTransfer): Promise<UploadFile[]> {
  const entries = Array.from(data.items)
    .map((item) => item.webkitGetAsEntry?.())
    .filter((e): e is FileSystemEntry => !!e);
  if (!entries.length) return fromInput(data.files);
  const out: UploadFile[] = [];
  await Promise.all(entries.map((e) => walk(e, out)));
  return out;
}

async function walk(entry: FileSystemEntry, out: UploadFile[]): Promise<void> {
  const path = entry.fullPath.replace(/^\//, "");
  if (entry.isFile) {
    const file = await new Promise<File>((res, rej) => (entry as FileSystemFileEntry).file(res, rej));
    out.push({ file, path });
    return;
  }
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  // readEntries devuelve por lotes, hay que llamarlo hasta que venga vacío
  while (true) {
    const batch = await new Promise<FileSystemEntry[]>((res, rej) => reader.readEntries(res, rej));
    if (!batch.length) break;
    await Promise.all(batch.map((e) => walk(e, out)));
  }
}

export function suggestedName(files: UploadFile[]): string {
  const roots = new Set(files.map((f) => f.path.split("/")[0]));
  if (roots.size === 1 && files[0]?.path.includes("/")) return [...roots][0];
  return "";
}
