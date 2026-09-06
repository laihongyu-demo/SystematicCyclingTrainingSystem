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
                  <th className="align-l">名称</th>
                  <th className="align-l">类型</th>
                  <th>距离</th>
                  <th>时长</th>
                  <th>爬升</th>
                  <th>均心率</th>
                  <th>加权功率</th>
                  <th>负荷</th>
                  <th>TSS</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id} title={a.device_name ?? undefined}>
                    <td className="align-l num">{fmtDate(a.start_date_local)}</td>
                    <td className="align-l">
                      {a.name ?? "—"}
                      {a.trainer ? <span className="tag trainer" style={{ marginLeft: 6 }}>滚筒</span> : null}
                    </td>
                    <td className="align-l">
                      <span className="tag">{TYPE_LABEL[a.type ?? ""] ?? a.type ?? "—"}</span>
                    </td>
                    <td className="num">{a.distance_km !== null ? `${fmtNum(a.distance_km, 1)}km` : "—"}</td>
                    <td className="num">{fmtDuration(a.moving_min)}</td>
                    <td className="num">{a.elevation_gain_m !== null ? fmtNum(a.elevation_gain_m, 0) + "m" : "—"}</td>
                    <td className="num">{a.average_heartrate !== null ? fmtNum(a.average_heartrate, 0) : "—"}</td>
                    <td className="num">{a.weighted_avg_watts !== null ? fmtNum(a.weighted_avg_watts, 0) + "w" : "—"}</td>
                    <td className="num">{a.training_load !== null ? fmtNum(a.training_load, 0) : "—"}</td>
                    <td className="num">{a.trimp !== null ? fmtNum(a.trimp, 0) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="heat-legend">
            <span>
              共 {total} 条活动（倒序），当前展示 {items.length} 条
            </span>
          </div>
        </>
      )}
    </div>
  );
}
