export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${(v < 10 ? v.toFixed(1) : String(Math.round(v))).replace(".", ",")} ${units[i]}`;
}

const rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });

export function relativeTime(seconds: number): string {
  const diff = Date.now() / 1000 - seconds;
  if (diff < 60) return "ahora mismo";
  if (diff < 3600) return rtf.format(-Math.floor(diff / 60), "minute");
  if (diff < 86400) return rtf.format(-Math.floor(diff / 3600), "hour");
  if (diff < 86400 * 7) return rtf.format(-Math.floor(diff / 86400), "day");
  return new Date(seconds * 1000).toLocaleDateString("es");
}

export type DateGroup = "Hoy" | "Ayer" | "Últimos 7 días" | "Anteriores";

export function dateGroup(seconds: number): DateGroup {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const today = startOfToday.getTime() / 1000;
  if (seconds >= today) return "Hoy";
  if (seconds >= today - 86400) return "Ayer";
  if (seconds >= today - 86400 * 7) return "Últimos 7 días";
  return "Anteriores";
}

export function plural(n: number, one: string, many: string): string {
  return `${n.toLocaleString("es")} ${n === 1 ? one : many}`;
}

export function basename(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

export function dirname(path: string): string {
  const parts = path.split(/[\\/]/);
  parts.pop();
  return parts.join("/");
}
