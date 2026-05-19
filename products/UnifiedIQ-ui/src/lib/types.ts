// Mirrors the backend domain models (app/models/domain.py, responses.py).

export type ChartType =
  | "line"
  | "bar"
  | "pie"
  | "area"
  | "scatter"
  | "table"
  | "none";

export interface ChartSpec {
  type: ChartType;
  title?: string | null;
  x?: string | null;
  y: string[];
  series?: string | null;
  stacked?: boolean;
}

export interface Citation {
  id: string;
  title: string;
  url?: string | null;
}

export interface ThinkingStep {
  step: string;
  detail: string;
}

export type Row = Record<string, unknown>;

export interface Alert {
  id: string;
  title: string;
  natural_language: string;
  metric_sql: string;
  comparator: "lt" | "lte" | "gt" | "gte" | "eq" | "neq";
  threshold: number;
  channel: "in_app" | "slack" | "email";
  recipient?: string | null;
  cadence_minutes: number;
  enabled: boolean;
  last_state: "pending" | "ok" | "breached" | "error";
  last_value?: number | null;
  last_checked_at?: string | null;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  created_at: string;
}
