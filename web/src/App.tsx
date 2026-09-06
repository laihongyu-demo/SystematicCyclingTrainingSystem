import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import type {
  ActivitiesResponse,
  CalendarResponse,
  FitnessResponse,
  OverviewResponse,
} from "./types";
import { useFetch } from "./hooks";
import OverviewCards from "./components/OverviewCards";
import ActivityList from "./components/ActivityList";
import CalendarHeatmap from "./components/CalendarHeatmap";
import SyncControl from "./components/SyncControl";
import { FitnessChart, LegendChips, WeeklyBars } from "./components/charts";

const RANGES = [
  { days: 30, label: "30天" },
  { days: 60, label: "60天" },
  { days: 90, label: "90天" },
];

function Panel({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="panel">
      <div className="section-head">
        <h2>{title}</h2>
        {hint ? <span className="hint">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}

export default function App() {
  // 主题（flat / light-dark）
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light",
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("sct-theme", theme);
  }, [theme]);
  const toggleTheme = useCallback(() => setTheme((t) => (t === "light" ? "dark" : "light")), []);

  // 时间窗口
  const [days, setDays] = useState(90);

  // 数据加载
  const overview = useFetch<OverviewResponse>(() => `/api/metrics/overview?days=${days}`, [days]);
  const fitness = useFetch<FitnessResponse>(
    () => `/api/metrics/fitness?days=${days}&mode=smooth`,
    [days],
  );
  const calendar = useFetch<CalendarResponse>(() => `/api/metrics/calendar?days=${days}`, [days]);
  const activities = useFetch<ActivitiesResponse>(
    () => `/api/activities?days=${days}&limit=200`,
    [days],
  );

  const reloadAll = useCallback(() => {
    overview.reload();
    fitness.reload();
    calendar.reload();
    activities.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const noData =
    !activities.loading &&
    !activities.error &&
    activities.data !== null &&
    activities.data.total === 0;

  const hasError =
    overview.error ?? fitness.error ?? calendar.error ?? activities.error ?? null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="logo">S</span>
            SCT 训练系统
          </div>
          <div className="spacer" />
          <div className="seg">
            {RANGES.map((r) => (
              <button
                key={r.days}
                className={days === r.days ? "active" : ""}
                onClick={() => setDays(r.days)}
              >
                {r.label}
              </button>
            ))}
          </div>
          <button className="icon-btn" onClick={toggleTheme} title="切换明暗主题">
            {theme === "light" ? "暗色" : "亮色"}
          </button>
        </div>
      </header>

      <main className="app-main">
        {hasError ? (
          <div className="banner-error">
            后端数据加载失败：{hasError}
            <button
              className="link"
              style={{ marginLeft: 10, background: "none", border: 0, cursor: "pointer" }}
              onClick={reloadAll}
            >
              重试
            </button>
          </div>
        ) : null}

        <Panel title="同步与数据" hint="从 intervals.icu 拉取活动并幂等写入本地">
          <SyncControl onSynced={reloadAll} />
        </Panel>

        {noData ? (
          <div className="panel" style={{ marginTop: 14 }}>
            <div className="empty-hint">本地暂无训练数据，点击上方「立即同步」拉取最近记录。</div>
          </div>
        ) : null}

        <section className="section">
          <OverviewCards data={overview.data} loading={overview.loading} error={overview.error} />
        </section>

        <section className="section">
          <div className="charts-grid">
            <Panel title="体能曲线" hint="CTL/ATL/TSB 逐日推演">
              {fitness.error ? (
                <div className="state-box error">{fitness.error}</div>
              ) : fitness.loading ? (
                <div className="state-box">加载曲线…</div>
              ) : (
                <>
                  <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
                    <LegendChips />
                  </div>
                  <FitnessChart series={fitness.data?.series ?? []} />
                </>
              )}
            </Panel>

            <Panel title="周负荷" hint="按 ISO 周聚合">
              {overview.loading ? (
                <div className="state-box">加载中…</div>
              ) : overview.error ? (
                <div className="state-box error">{overview.error}</div>
              ) : (
                <WeeklyBars weeks={overview.data?.weekly ?? []} />
              )}
            </Panel>
          </div>
        </section>

        <section className="section">
          <Panel title="训练日历" hint="按日负荷着色，悬停查看详情">
            {calendar.error ? (
              <div className="state-box error">{calendar.error}</div>
            ) : calendar.loading ? (
              <div className="state-box">加载日历…</div>
            ) : calendar.data && calendar.data.days.length > 0 ? (
              <CalendarHeatmap days={calendar.data.days} window={calendar.data.window} />
            ) : (
              <div className="empty-hint">窗口内暂无训练记录（需先完成同步）</div>
            )}
          </Panel>
        </section>

        <section className="section">
          <Panel title="活动列表" hint={`近 ${days} 天，按开始时间倒序`}>
            <ActivityList
              items={activities.data?.items ?? []}
              total={activities.data?.total ?? 0}
              loading={activities.loading}
              error={activities.error}
            />
          </Panel>
        </section>
      </main>
    </div>
  );
}
