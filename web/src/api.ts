// 统一的 /api 请求层：vite 开发期经代理转发到 FastAPI(127.0.0.1:8000)
import type {
  ActivitiesResponse,
  CalendarResponse,
  Capability,
  FitnessResponse,
  HealthDailyResponse,
  MorningRhrResponse,
  MorningRhrResult,
  OverviewResponse,
  SyncLogEntry,
  SyncStatusResponse,
  WeeklyResponse,
} from "./types";

export class ApiError extends Error {
  status: number | null;
  constructor(message: string, status: number | null = null) {
    super(message);
    this.status = status;
  }
}

async function readBody(res: Response): Promise<string> {
  let detail = `HTTP ${res.status} ${res.statusText}`;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (body.detail !== undefined) detail = String(body.detail);
  } catch {
    /* 保留默认错误信息 */
  }
  return detail;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
      ...init,
    });
  } catch {
    throw new ApiError("无法连接后端服务，请确认 FastAPI 已在 127.0.0.1:8000 启动");
  }
  if (!res.ok) {
    throw new ApiError(await readBody(res), res.status);
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
  capability: () => getJSON<Capability>("/api/metrics/capability"),
  healthDaily: (days: number) => getJSON<HealthDailyResponse>(`/api/wellness/daily?days=${days}`),
  morningRhr: (days: number) => getJSON<MorningRhrResponse>(`/api/wellness/morning-rhr?days=${days}`),
  morningRhrSave: (payload: { date: string; value: number; note?: string | null; overwrite?: boolean }) =>
    request<MorningRhrResult>("/api/wellness/morning-rhr", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

async function getJSON<T>(url: string): Promise<T> {
  return request<T>(url);
}

export async function runSync(): Promise<SyncLogEntry> {
  return request<SyncLogEntry>("/api/sync/activities", { method: "POST", body: "{}" });
}
