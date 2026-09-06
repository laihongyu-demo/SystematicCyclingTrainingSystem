// 统一的 /api 请求层：vite 开发期经代理转发到 FastAPI(127.0.0.1:8000)
import type {
  ActivitiesResponse,
  CalendarResponse,
  FitnessResponse,
  OverviewResponse,
  SyncLogEntry,
  SyncStatusResponse,
  WeeklyResponse,
} from "./types";

export class ApiError extends Error {}

async function getJSON<T>(url: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError("无法连接后端服务，请确认 FastAPI 已在 127.0.0.1:8000 启动");
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body.detail !== undefined) detail = String(body.detail);
    } catch {
      /* 保留默认错误信息 */
    }
    throw new ApiError(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  overview: (days: number) => getJSON<OverviewResponse>(`/api/metrics/overview?days=${days}`),
  fitness: (days: number) => getJSON<FitnessResponse>(`/api/metrics/fitness?days=${days}&mode=smooth`),
  weekly: (days: number) => getJSON<WeeklyResponse>(`/api/metrics/weekly?days=${days}`),
  calendar: (days: number) => getJSON<CalendarResponse>(`/api/metrics/calendar?days=${days}`),
  activities: (days: number, limit = 100) =>
    getJSON<ActivitiesResponse>(`/api/activities?days=${days}&limit=${limit}`),
  syncStatus: () => getJSON<SyncStatusResponse>("/api/sync/status"),
};

export async function runSync(): Promise<SyncLogEntry> {
  let res: Response;
  try {
    res = await fetch("/api/sync/activities", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
  } catch {
    throw new ApiError("无法连接后端服务，同步失败");
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body.detail !== undefined) detail = String(body.detail);
    } catch {
      /* 保留默认错误信息 */
    }
    throw new ApiError(detail);
  }
  return (await res.json()) as SyncLogEntry;
}
