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
  scheduled_at?: string | null;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  created_at: string;
}

export interface ViewLayout {
  w: 1 | 2;
  h: 1 | 2;
  position: number;
}

export interface ViewSpec {
  question: string;
  sql: string;
  chart_config?: ChartSpec | null;
  default_view: "bar" | "line" | "area" | "pie" | "table" | "kpi";
  filter_text?: string | null;
  layout?: ViewLayout | null;
  colors?: string[] | null;
  x_label?: string | null;
  y_label?: string | null;
  canvas_id?: string | null;
}

export interface UserView {
  id: string;
  user_email?: string;
  name: string;
  kind: "chart" | "table" | "dashboard";
  spec: ViewSpec;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
}

export interface Canvas {
  id: string;
  user_email?: string;
  name: string;
  status: "draft" | "published";
  source_canvas_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ViewRunResult {
  view: UserView;
  rows: Row[];
}

export interface UserMemory {
  id: string;
  value: string;
  created_at: string;
  updated_at: string;
}

export interface VerificationResult {
  verdict: "agree" | "disagree" | "inconclusive";
  confidence: number;
  original_value?: number | null;
  alternative_value?: number | null;
  alternative_sql: string;
  alternative_approach: string;
  rationale: string;
  diff_pct?: number | null;
}
