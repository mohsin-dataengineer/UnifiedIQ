"use client";

import {
  BarChart3,
  Download,
  LineChart as LineIcon,
  PieChart as PieIcon,
  Table as TableIcon,
  AreaChart as AreaIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { ChartRenderer } from "@/components/chat/chart-renderer";
import { DataTable } from "@/components/chat/data-table";
import { Segmented } from "@/components/ui/segmented";
import {
  columnsOf,
  downloadCsv,
  fmtValue,
  humanize,
  isNumeric,
  numericColumns,
} from "@/lib/format";
import type { ChartSpec, Row } from "@/lib/types";

function KpiCards({ row }: { row: Row }) {
  const cols = Object.keys(row);
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {cols.map((c) => (
        <div
          key={c}
          className="rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-3"
        >
          <div className="text-xs font-medium tracking-wide text-[var(--muted)] uppercase">
            {humanize(c)}
          </div>
          <div
            className={
              isNumeric(row[c])
                ? "mt-1 text-2xl font-semibold text-[var(--fg)]"
                : "mt-1 text-lg font-medium text-[var(--fg)]"
            }
          >
            {fmtValue(row[c])}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ResultView({
  spec,
  data,
}: {
  spec?: ChartSpec;
  data: Row[];
}) {
  const cols = columnsOf(data);
  const nums = numericColumns(data);
  const x = spec?.x || cols.find((c) => !nums.includes(c)) || cols[0] || "";
  const y = spec?.y?.length ? spec.y : nums;

  const singleRow = data.length === 1;
  const chartable = !singleRow && !!x && y.length > 0;

  const [view, setView] = useState<string>(() => {
    if (singleRow) return "kpi";
    if (spec && ["bar", "line", "area", "pie"].includes(spec.type)) {
      return spec.type;
    }
    return chartable ? "bar" : "table";
  });

  const options = useMemo(
    () => [
      { value: "table", label: "Table", icon: <TableIcon size={13} /> },
      {
        value: "bar",
        label: "Bar",
        icon: <BarChart3 size={13} />,
        disabled: !chartable,
      },
      {
        value: "line",
        label: "Line",
        icon: <LineIcon size={13} />,
        disabled: !chartable,
      },
      {
        value: "area",
        label: "Area",
        icon: <AreaIcon size={13} />,
        disabled: !chartable,
      },
      {
        value: "pie",
        label: "Pie",
        icon: <PieIcon size={13} />,
        disabled: !chartable || y.length !== 1,
      },
    ],
    [chartable, y.length],
  );

  if (!data.length) return null;

  return (
    <div className="mt-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium text-[var(--muted)]">
          {data.length.toLocaleString()} row
          {data.length === 1 ? "" : "s"}
        </span>
        <div className="flex items-center gap-2">
          {!singleRow && (
            <Segmented options={options} value={view} onChange={setView} />
          )}
          <button
            type="button"
            onClick={() => downloadCsv(data)}
            className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] transition-colors hover:text-[var(--fg)]"
          >
            <Download size={13} /> CSV
          </button>
        </div>
      </div>

      {view === "kpi" ? (
        <KpiCards row={data[0]} />
      ) : view === "table" ? (
        <DataTable rows={data} />
      ) : (
        <ChartRenderer
          type={view as "bar" | "line" | "area" | "pie"}
          x={x}
          y={y}
          data={data}
        />
      )}
    </div>
  );
}
