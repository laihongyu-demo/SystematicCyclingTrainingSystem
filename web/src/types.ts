// 与 FastAPI 返回结构一一对应（见 app/api/* 与 app/services/metrics_service.py）

export interface FitnessPoint {
  date: string;
  ctl: number | null;
  atl: number | null;
  tsb: number | null;
  load?: number | null;
}

export interface WeekRow {
  week_start: string;
  activities: number;
  distance_km: number;
  moving_h: number;
  load: number;
  trimp: number;
}

export interface CalendarDay {
  date: string;
  activities: number;
  load: number;
  distance_km: number;
  moving_min: number;
}

export interface ActivityItem {
  id: string;
  name: string | null;
  type: string | null;
  start_date_local: string | null;
  distance_km: number | null;
  moving_min: number | null;
  elevation_gain_m: number | null;
  average_heartrate: number | null;
  max_heartrate: number | null;
  average_cadence: number | null;
  average_watts: number | null;
  weighted_avg_watts: number | null;
  training_load: number | null;
  trimp: number | null;
  ctl: number | null;
  atl: number | null;
  tsb: number | null;
  trainer: boolean | null;
  device_name: string | null;
}

export interface Window {
  oldest: string;
  newest: string;
}

export interface OverviewResponse {
  window: Window;
  workout_days: number;
  weekly: WeekRow[];
  current: FitnessPoint | null;
  summary: {
    activities: number;
    distance_km: number;
    moving_h: number;
    load: number;
  };
}

export interface FitnessResponse {
  mode: string;
  window: Window;
  series: FitnessPoint[];
}

export interface WeeklyResponse {
  window: Window;
  weeks: WeekRow[];
}

export interface CalendarResponse {
  window: Window;
  days: CalendarDay[];
}

export interface ActivitiesResponse {
  total: number;
  items: ActivityItem[];
}

export interface SyncLogEntry {
  id: number;
  scope: string;
  status: string;
  window_oldest?: string;
  window_newest?: string;
  inserted: number;
  updated: number;
  unchanged: number;
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface SyncStatusResponse {
  recent: SyncLogEntry[];
}
