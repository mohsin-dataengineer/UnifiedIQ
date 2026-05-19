"use client";

import { columnsOf, fmtValue, humanize } from "@/lib/format";
import type { Row } from "@/lib/types";

export function DataTable({ rows }: { rows: Row[] }) {
  if (!rows.length) {
    return (
      <p className="px-4 py-6 text-center text-sm text-[var(--muted)]">
        No rows returned.
      </p>
    );
  }
  const cols = columnsOf(rows);
  return (
    <div className="max-h-80 overflow-auto rounded-lg border border-[var(--border)]">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 bg-[var(--bg)]">
          <tr>
            {cols.map((c) => (
              <th
                key={c}
                className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--fg)] whitespace-nowrap"
              >
                {humanize(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 200).map((r, i) => (
            <tr
              key={i}
              className={i % 2 ? "bg-[var(--bg)]/40" : "bg-[var(--surface)]"}
            >
              {cols.map((c) => (
                <td
                  key={c}
                  className="border-b border-[var(--border)] px-3 py-1.5 whitespace-nowrap text-[var(--fg)]"
                >
                  {fmtValue(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
