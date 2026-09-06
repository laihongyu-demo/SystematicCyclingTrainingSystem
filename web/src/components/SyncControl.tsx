import { useCallback, useState } from "react";
import { runSync } from "../api";
import { fmtDateTime, useFetch } from "../hooks";
import type { SyncLogEntry, SyncStatusResponse } from "../types";

function SyncStatusText({ log }: { log: SyncLogEntry | undefined }) {
  if (!log) return <span>尚未执行同步</span>;
  if (log.status === "success") {
    return (
      <span>
        上次同步 {fmtDateTime(log.finished_at)} · 新增 {log.inserted} / 更新 {log.updated} / 未变{" "}
        {log.unchanged}
      </span>
    );
  }
  return <span>上次同步失败{log.error ? `：${log.error}` : ""}</span>;
}

export default function SyncControl({ onSynced }: { onSynced: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { data, reload } = useFetch<SyncStatusResponse>(() => "/api/sync/status", []);

  const lastLog = data?.recent?.[0];

  const doSync = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const log = await runSync();
      if (log.status === "success") {
        setMsg(`同步完成：新增 ${log.inserted}，更新 ${log.updated}，未变 ${log.unchanged}`);
      } else {
        setErr(`同步失败：${log.error ?? "未知错误"}`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      reload();
      onSynced();
    }
  }, [busy, onSynced, reload]);

  return (
    <div>
      <div className="meta-line" style={{ gap: 12 }}>
        <button className="btn primary" onClick={doSync} disabled={busy}>
          {busy ? <span className="spinner" /> : null}
          {busy ? "同步中…" : "立即同步"}
        </button>
        <span className={`dot ${lastLog?.status === "success" ? "ok" : lastLog?.status === "failed" ? "err" : ""}`} />
        <SyncStatusText log={lastLog} />
      </div>
      {msg ? <div className="sync-msg ok-msg">{msg}</div> : null}
      {err ? <div className="sync-msg err-msg">{err}</div> : null}
    </div>
  );
}
