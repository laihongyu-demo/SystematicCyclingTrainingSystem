import { useMemo, useState } from "react";
import type { ActivityItem } from "../types";
import { fmtDate, fmtDuration, fmtNum } from "../hooks";

const TYPE_LABEL: Record<string, string> = {
  Ride: "骑行",
  VirtualRide: "虚拟骑行",
  IndoorRide: "室内骑行",
  Workout: "训练",
  Run: "跑步",
  Swim: "游泳",
  WeightTraining: "力量",
};

/** 默认仅展示近 RECENT_DAYS 天的活动，更早的折叠显示。 */
const RECENT_DAYS = 14;
const DAY_MS = 86_400_000;

/** 室内/户外区分：trainer=true 或虚拟/室内类型 → 室内骑行；普通骑行 → 公路骑行。 */
function envTagOf(a: ActivityItem): string | null {
  if (
    a.trainer === true ||
    a.type === "VirtualRide" ||
    a.type === "IndoorRide"
  ) {
    return "室内骑行";
  }
  if (a.type === "Ride") return "公路骑行";
  return null;
}

function fmtWatts(v: number | null | undefined): string {
  return v !== null && v !== undefined ? `${fmtNum(v, 0)}w` : "—";
}

export default function ActivityList({
  items,
  total,
  loading,
  error,
}: {
  items: ActivityItem[];
  total: number;
  loading: boolean;
  error: string | null;
}) {
  const [expanded, setExpanded] = useState(false);

  const recentCount = useMemo(() => {
    const cutoff = Date.now() - RECENT_DAYS * DAY_MS;
    return items.reduce((n, a) => {
      const s = a.start_date_local;
      if (!s) return n;
      const t = new Date(s).getTime();
      return !Number.isNaN(t) && t >= cutoff ? n + 1 : n;
    }, 0);
  }, [items]);

  // 近期无数据时整表展示，避免“空白首屏”；否则默认只展示近期子集
  const showRecentOnly = !expanded && recentCount > 0 && recentCount < items.length;
  const visible = showRecentOnly ? items.slice(0, recentCount) : items;
  const older = items.length - recentCount;

  if (loading) return <div className="state-box">加载活动列表…</div>;
  if (error) return <div className="state-box error">{error}</div>;

  return (
    <div>
      {items.length === 0 ? (
        <div className="empty-hint">窗口内暂无活动记录（需先完成同步）</div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th className="align-l">日期</th>
                  <th className="align-l">活动</th>
                  <th className="align-l">类型</th>
                  <th>距离</th>
                  <th>时长</th>
                  <th>平均心率</th>
                  <th>平均功率(AP)</th>
                  <th>标准化功率(NP)</th>
                  <th>踏频</th>
                  <th>爬升</th>
                  <th title="intervals.icu 训练负荷（用于 CTL/ATL 计算）">负荷</th>
                  <th title="TRIMP：基于心率的压力分，口径不同于上方负荷">TRIMP</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((a) => {
                  const env = envTagOf(a);
                  return (
                    <tr key={a.id} title={a.device_name ?? undefined}>
                      <td className="align-l num">{fmtDate(a.start_date_local)}</td>
                      <td className="align-l">
                        {a.name ?? "—"}
                        {env ? (
                          <span
                            className={`tag ${env === "室内骑行" ? "tag-indoor" : "tag-road"}`}
                            style={{ marginLeft: 6 }}
                          >
                            {env}
                          </span>
                        ) : null}
                      </td>
                      <td className="align-l">
                        <span className="tag">{TYPE_LABEL[a.type ?? ""] ?? a.type ?? "—"}</span>
                      </td>
                      <td className="num">{a.distance_km !== null ? `${fmtNum(a.distance_km, 1)}km` : "—"}</td>
                      <td className="num">{fmtDuration(a.moving_min)}</td>
                      <td className="num">{a.average_heartrate !== null ? `${fmtNum(a.average_heartrate, 0)}` : "—"}</td>
                      <td className="num">{fmtWatts(a.average_watts)}</td>
                      <td className="num">{fmtWatts(a.weighted_avg_watts)}</td>
                      <td className="num">{a.average_cadence !== null ? `${fmtNum(a.average_cadence, 0)}rpm` : "—"}</td>
                      <td className="num">{a.elevation_gain_m !== null ? fmtNum(a.elevation_gain_m, 0) + "m" : "—"}</td>
                      <td className="num">{a.training_load !== null ? fmtNum(a.training_load, 0) : "—"}</td>
                      <td className="num">{a.trimp !== null ? fmtNum(a.trimp, 0) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="heat-legend">
            <span>
              共 {total} 条活动（倒序）
              {showRecentOnly ? `，当前展示近 ${RECENT_DAYS} 天 ${visible.length} 条` : ""}
            </span>
            {older > 0 ? (
              <button className="btn" style={{ marginLeft: "auto" }} onClick={() => setExpanded((e) => !e)}>
                {expanded ? "收起早期记录" : `展开更早记录（${older} 条）`}
              </button>
            ) : null}
          </div>
          <div className="hint" style={{ marginTop: 6 }}>
            口径：负荷 = intervals.icu 训练负荷（驱动 CTL/ATL）；TRIMP = 基于心率（及功率/配速）的强度分，两者计法不同故数值不同。
          </div>
        </>
      )}
    </div>
  );
}
