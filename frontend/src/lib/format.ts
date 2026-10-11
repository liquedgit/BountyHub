function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(value: string | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return "—";
  return d.toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function formatRelative(value: string | Date | null | undefined, now: Date = new Date()): string {
  const d = toDate(value);
  if (!d) return "—";
  const diff = Math.round((now.getTime() - d.getTime()) / 1000);
  const abs = Math.abs(diff);
  if (abs < 45) return "just now";
  const units: [number, string][] = [
    [60, "minute"], [60 * 60, "hour"], [60 * 60 * 24, "day"],
    [60 * 60 * 24 * 30, "month"], [60 * 60 * 24 * 365, "year"],
  ];
  let unit = "minute";
  let size = 60;
  for (const [s, name] of units) {
    if (abs >= s) {
      unit = name;
      size = s;
    }
  }
  const n = Math.max(1, Math.round(abs / size));
  const label = `${n} ${unit}${n === 1 ? "" : "s"}`;
  return diff >= 0 ? `${label} ago` : `in ${label}`;
}

export function formatMoney(cents: number | null | undefined): string {
  if (cents == null) return "—";
  return (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function formatDuration(
  start: string | Date | null | undefined,
  end?: string | Date | null,
): string {
  const s = toDate(start);
  if (!s) return "—";
  const e = toDate(end) ?? new Date();
  let secs = Math.max(0, Math.round((e.getTime() - s.getTime()) / 1000));
  const h = Math.floor(secs / 3600);
  secs -= h * 3600;
  const m = Math.floor(secs / 60);
  secs -= m * 60;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${secs}s`;
  return `${secs}s`;
}
