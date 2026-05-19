import type { Row } from "@/lib/types";

const NUM = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

export function isNumeric(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

export function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (isNumeric(v)) return NUM.format(v);
  return String(v);
}

export function humanize(col: string): string {
  return col
    .replace(/[_.]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

export function columnsOf(rows: Row[]): string[] {
  return rows.length ? Object.keys(rows[0]) : [];
}

export function numericColumns(rows: Row[]): string[] {
  if (!rows.length) return [];
  return columnsOf(rows).filter((c) => isNumeric(rows[0][c]));
}

export function toCsv(rows: Row[]): string {
  if (!rows.length) return "";
  const cols = columnsOf(rows);
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [
    cols.join(","),
    ...rows.map((r) => cols.map((c) => esc(r[c])).join(",")),
  ].join("\n");
}

export function downloadCsv(rows: Row[], name = "unifiediq-result"): void {
  const blob = new Blob([toCsv(rows)], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
