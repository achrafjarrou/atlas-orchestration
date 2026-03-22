/**
 * ATLAS Dashboard — AI Workstation 2026
 *
 * Design goals:
 * - Show A2A protocol in action (live agent graph)
 * - Show SHA-256 audit chain growing in real time
 * - Show HITL workflow (pause → approve → resume)
 * - Show performance metrics that prove production-readiness
 * - Signal: "this engineer builds things that work"
 */

import React, { useState, useEffect, useRef, useCallback } from "react";

// ── Config ────────────────────────────────────────────────────────────────────
const API = window.location.hostname === "localhost"
  ? "http://localhost:8000"
  : "https://achrafjarrou-atlas-orchestration.hf.space";

// ── Types ─────────────────────────────────────────────────────────────────────
interface Agent   { agent_id:string; name:string; base_url:string; status:string; health_score:number; capabilities?:any[]; }
interface Task    { task_id:string; status:string; result:string|null; requires_hitl:boolean; hitl_reason?:string; routing?:{agent:string;score:number;routing_ms?:number}; duration_ms?:number; }
interface Audit   { id:string; action:string; agent_id:string; record_hash:string; created_at:string; status:string; intent?:string; task_id?:string; }
interface Health  { status:string; version:string; uptime_s:number; services:Record<string,string>; metrics:Record<string,number>; }
interface Metrics { tasks_total:number; tasks_completed:number; hitl_triggered:number; avg_routing_ms:number; audit_chain_length:number; agents_online:number; uptime_s:number; }

// ── API helpers ───────────────────────────────────────────────────────────────
async function apiFetch<T>(path:string, opts?:RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    headers: {"Content-Type":"application/json"}, ...opts,
  });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}
const GET  = <T,>(p:string) => apiFetch<T>(p);
const POST = <T,>(p:string, b:any) => apiFetch<T>(p, {method:"POST",body:JSON.stringify(b)});

function usePoll(fn:()=>void, ms:number, immediate=true) {
  useEffect(() => {
    if (immediate) fn();
    const id = setInterval(fn, ms);
    return () => clearInterval(id);
  }, []);
}

// ── Primitive UI ──────────────────────────────────────────────────────────────
const cx = (...args: (string|false|undefined)[]) => args.filter(Boolean).join(" ");

function Glow({ color="blue" }: { color?:string }) {
  const colors: Record<string,string> = {
    blue:"bg-blue-500", teal:"bg-teal-500", green:"bg-emerald-500",
    amber:"bg-amber-500", red:"bg-red-500", purple:"bg-purple-500", orange:"bg-orange-500",
  };
  return (
    <span className="relative flex h-2 w-2 flex-shrink-0">
      <span className={cx("animate-ping absolute inline-flex h-full w-full rounded-full opacity-60", colors[color])} />
      <span className={cx("relative inline-flex rounded-full h-2 w-2", colors[color])} />
    </span>
  );
}

function Chip({ label, color="gray" }: { label:string; color?:string }) {
  const map: Record<string,string> = {
    completed:"text-emerald-300 bg-emerald-950 border-emerald-800/60",
    active:   "text-emerald-300 bg-emerald-950 border-emerald-800/60",
    ok:       "text-emerald-300 bg-emerald-950 border-emerald-800/60",
    working:  "text-blue-300 bg-blue-950 border-blue-800/60",
    submitted:"text-sky-300 bg-sky-950 border-sky-800/60",
    hitl_pending:"text-orange-300 bg-orange-950 border-orange-800/60",
    failed:   "text-red-300 bg-red-950 border-red-800/60",
    cancelled:"text-gray-400 bg-gray-900 border-gray-700/60",
    inactive: "text-gray-500 bg-gray-900 border-gray-700/60",
    gray:     "text-gray-400 bg-gray-900 border-gray-700/60",
  };
  const cls = map[label] ?? map[color] ?? map.gray;
  return <span className={cx("text-[10px] font-mono px-2 py-0.5 rounded-full border font-medium", cls)}>{label}</span>;
}

function Panel({
  title, sub, accent="blue", children, right, className="",
}: {
  title:string; sub?:string; accent?:string; children:React.ReactNode;
  right?:React.ReactNode; className?:string;
}) {
  const borders: Record<string,string> = {
    blue:"border-blue-500/20", teal:"border-teal-500/20", green:"border-emerald-500/20",
    amber:"border-amber-500/20", purple:"border-purple-500/20", orange:"border-orange-500/20",
  };
  const dots: Record<string,string> = {
    blue:"bg-blue-500", teal:"bg-teal-500", green:"bg-emerald-500",
    amber:"bg-amber-500", purple:"bg-purple-500", orange:"bg-orange-500",
  };
  return (
    <div className={cx(
      "rounded-2xl border bg-gray-950/80 backdrop-blur-sm flex flex-col",
      borders[accent] ?? borders.blue, className,
    )}>
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/5">
        <div className="flex items-center gap-2.5">
          <div className={cx("w-1 h-5 rounded-full", dots[accent] ?? dots.blue)} />
          <div>
            <div className="text-xs font-semibold text-white tracking-wider uppercase">{title}</div>
            {sub && <div className="text-[10px] text-gray-600 mt-0.5">{sub}</div>}
          </div>
        </div>
        {right}
      </div>
      <div className="p-5 flex-1 flex flex-col">{children}</div>
    </div>
  );
}

function StatCard({ label, value, sub, color="white" }: { label:string; value:string|number; sub?:string; color?:string }) {
  const colors: Record<string,string> = {
    white:"text-white", blue:"text-blue-400", teal:"text-teal-400",
    green:"text-emerald-400", amber:"text-amber-400", red:"text-red-400",
  };
  return (
    <div className="bg-white/[0.03] border border-white/5 rounded-xl p-3 text-center">
      <div className={cx("text-xl font-bold font-mono", colors[color] ?? colors.white)}>{value}</div>
      <div className="text-[10px] text-gray-600 uppercase tracking-wider mt-0.5">{label}</div>
      {sub && <div className="text-[10px] text-gray-700 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Panel: System Status ──────────────────────────────────────────────────────
function SystemPanel() {
  const [h, setH]   = useState<Health|null>(null);
  const [m, setM]   = useState<Metrics|null>(null);
  const [err, setErr] = useState(false);

  usePoll(() => {
    GET<Health>("/health").then(setH).catch(() => setErr(true));
    GET<Metrics>("/api/v1/metrics").then(setM).catch(() => {});
  }, 4000);

  const uptime = m ? `${Math.floor(m.uptime_s/3600)}h ${Math.floor((m.uptime_s%3600)/60)}m` : "--";

  return (
    <Panel title="System" sub="A2A v0.3 · LangGraph · MCP · SHA-256" accent="blue"
      right={h ? <span className="flex items-center gap-1.5"><Glow color="green" /><span className="text-[10px] text-emerald-400 font-mono">LIVE</span></span> : null}>
      {err && !h && (
        <div className="text-amber-400 text-xs font-mono">
          API offline<br/><span className="text-gray-600">poetry run python -m atlas.api.main</span>
        </div>
      )}
      {h && (
        <>
          <div className="grid grid-cols-2 gap-2 mb-4">
            <StatCard label="Uptime" value={uptime} color="blue" />
            <StatCard label="Version" value={h.version} sub="atlas" color="teal" />
            {m && <StatCard label="Tasks" value={m.tasks_total} sub={`${m.tasks_completed} completed`} color="green" />}
            {m && <StatCard label="Agents" value={m.agents_online} sub="online" color="amber" />}
          </div>
          <div className="space-y-1.5 flex-1">
            {Object.entries(h.services).slice(0,8).map(([k,v]) => (
              <div key={k} className="flex items-center justify-between bg-white/[0.02] hover:bg-white/[0.04] rounded-lg px-3 py-1.5 transition-colors">
                <span className="text-[11px] text-gray-500 font-mono">{k}</span>
                <div className="flex items-center gap-1.5">
                  <Glow color={v.startsWith("ok") ? "green" : "red"} />
                  <span className={cx("text-[10px] font-mono", v.startsWith("ok") ? "text-emerald-400" : "text-red-400")}>
                    {v.startsWith("ok") ? v.slice(0,20) : "error"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      {!h && !err && <div className="text-gray-700 text-xs animate-pulse">Connecting to ATLAS API...</div>}
    </Panel>
  );
}

// ── Panel: Agent Network ──────────────────────────────────────────────────────
function AgentPanel() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [url, setUrl]       = useState("");
  const [registering, setReg] = useState(false);

  usePoll(() => GET<Agent[]>("/api/v1/agents").then(setAgents).catch(() => {}), 6000);

  const register = async () => {
    if (!url.trim()) return;
    setReg(true);
    await POST("/api/v1/agents/register", {url, name:`Agent @ ${url}`}).catch(() => {});
    const fresh = await GET<Agent[]>("/api/v1/agents").catch(() => agents);
    setAgents(fresh);
    setUrl("");
    setReg(false);
  };

  const dotColor = (s:string) => s==="active" ? "green" : "red";

  return (
    <Panel title="Agent Network" sub="A2A Protocol v0.3 — registered agents" accent="teal"
      right={<span className="text-[10px] text-teal-500 font-mono border border-teal-500/20 px-2 py-0.5 rounded">{agents.length} nodes</span>}>
      <div className="space-y-2 mb-3 flex-1 overflow-y-auto max-h-64">
        {agents.map(a => (
          <div key={a.agent_id}
            className="flex items-start gap-3 bg-white/[0.02] hover:bg-white/[0.04] rounded-xl px-3 py-2.5 transition-colors cursor-default group">
            <Glow color={dotColor(a.status)} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2 mb-0.5">
                <span className="text-xs font-semibold text-white truncate">{a.name}</span>
                <span className="text-[10px] text-gray-600">{Math.round((a.health_score??1)*100)}%</span>
              </div>
              <div className="text-[10px] text-gray-700 font-mono truncate mb-1">{a.base_url}</div>
              {a.capabilities && (
                <div className="flex flex-wrap gap-1">
                  {a.capabilities.slice(0,3).map((c:any) => (
                    <span key={c.id} className="text-[9px] text-gray-600 bg-white/5 px-1.5 py-0.5 rounded">{c.id}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {agents.length === 0 && <div className="text-center py-6 text-gray-700 text-xs">No agents yet</div>}
      </div>
      <div className="flex gap-2 mt-auto">
        <input
          className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-teal-500/40 placeholder:text-gray-700"
          placeholder="http://my-agent:8001"
          value={url}
          onChange={e => setUrl(e.target.value)}
          onKeyDown={e => e.key==="Enter" && register()}
        />
        <button onClick={register} disabled={registering}
          className="text-xs bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/30 text-teal-300 px-3 py-2 rounded-lg transition-colors font-semibold">
          {registering ? "..." : "Register"}
        </button>
      </div>
    </Panel>
  );
}

// ── Panel: Task Terminal ──────────────────────────────────────────────────────
function TaskPanel() {
  const [input, setInput]     = useState("");
  const [task, setTask]       = useState<Task|null>(null);
  const [loading, setLoading] = useState(false);
  const [logs, setLogs]       = useState<{t:string;msg:string;type:string}[]>([]);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const log = (msg:string, type="info") => {
    const t = new Date().toLocaleTimeString("en",{hour12:false,hour:"2-digit",minute:"2-digit",second:"2-digit"});
    setLogs(l => [...l.slice(-30), {t,msg,type}]);
  };

  useEffect(() => { logRef.current?.scrollTo(0, logRef.current.scrollHeight); }, [logs]);

  const EXAMPLES = [
    "analyze this NDA for GDPR violations",
    "check EU AI Act Article 9 compliance for my system",
    "delete all records from production database",
    "search for latest A2A protocol updates",
    "generate a Python script to parse this JSON",
  ];

  const run = async (msg?: string) => {
    const message = msg || input.trim();
    if (!message || loading) return;
    setLoading(true);
    setTask(null);

    log(`→ SUBMIT "${message.slice(0,55)}..."`, "submit");
    log(`  routing: semantic_embedding + Qdrant`, "info");

    try {
      const r = await POST<{task_id:string;status:string;requires_hitl:boolean}>("/api/v1/tasks", {message});
      log(`✓ task_id: ${r.task_id.slice(-10)}`, "ok");
      log(`  status: ${r.status}`, r.requires_hitl ? "warn" : "ok");
      if (r.requires_hitl) {
        log(`⏸ HITL: human approval required`, "warn");
      }

      for (let i = 0; i < 40; i++) {
        await new Promise(res => setTimeout(res, 600));
        const t = await GET<Task>(`/api/v1/tasks/${r.task_id}`);
        setTask(t);
        if (t.status === "working" && i === 0) log(`  pipeline: intent → route → call → audit`, "info");
        if (t.routing?.routing_ms && i < 2) log(`  routing_ms: ${t.routing.routing_ms}ms`, "ok");
        if (["completed","failed","hitl_pending","cancelled"].includes(t.status)) {
          log(`✓ ${t.status} (${t.duration_ms ?? "--"}ms total)`, t.status === "completed" ? "ok" : "warn");
          break;
        }
      }
    } catch(e:any) {
      log(`✗ ${String(e)}`, "error");
    }
    setLoading(false);
    if (!msg) setInput("");
  };

  const hitl = async (decision:"approve"|"reject") => {
    if (!task) return;
    log(`→ HITL: ${decision.toUpperCase()}`, decision==="approve" ? "ok" : "warn");
    const r = await POST<Task>(`/api/v1/tasks/${task.task_id}/hitl`, {decision});
    setTask(r);
    if (decision === "approve") {
      log(`  pipeline resuming...`, "info");
      for (let i = 0; i < 20; i++) {
        await new Promise(res => setTimeout(res, 700));
        const t = await GET<Task>(`/api/v1/tasks/${task.task_id}`);
        setTask(t);
        if (["completed","failed"].includes(t.status)) {
          log(`✓ ${t.status} after HITL approval`, "ok");
          break;
        }
      }
    } else {
      log(`  task cancelled by reviewer`, "warn");
    }
  };

  const logColor: Record<string,string> = {
    submit:"text-blue-400", ok:"text-emerald-400", warn:"text-orange-400",
    error:"text-red-400", info:"text-gray-600",
  };

  return (
    <Panel title="Task Terminal" sub="Submit → Route → Execute → Audit" accent="purple">
      {/* Log */}
      <div ref={logRef}
        className="bg-black/50 rounded-xl p-4 font-mono text-[11px] h-40 overflow-y-auto mb-4 border border-white/5 flex-shrink-0">
        {logs.length === 0
          ? <div className="text-gray-700">// ATLAS pipeline ready — submit a task below<br/>// try: "analyze this contract for GDPR" or "delete all production data"</div>
          : logs.map((l,i) => (
            <div key={i} className="leading-relaxed">
              <span className="text-gray-700">{l.t} </span>
              <span className={logColor[l.type] ?? "text-gray-500"}>{l.msg}</span>
            </div>
          ))
        }
      </div>

      {/* HITL */}
      {task?.requires_hitl && task.status === "hitl_pending" && (
        <div className="mb-4 bg-orange-950/40 border border-orange-500/30 rounded-xl p-4 flex-shrink-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-orange-400 text-sm">⏸</span>
            <span className="text-xs font-bold text-orange-300 uppercase tracking-wider">Human Approval Required</span>
          </div>
          <div className="text-[11px] text-orange-200/50 font-mono mb-3">{task.hitl_reason}</div>
          <div className="flex gap-2">
            <button onClick={() => hitl("approve")}
              className="flex-1 text-xs bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 py-2 rounded-lg font-bold transition-colors">
              ✓ APPROVE — Resume pipeline
            </button>
            <button onClick={() => hitl("reject")}
              className="flex-1 text-xs bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-300 py-2 rounded-lg font-bold transition-colors">
              ✕ REJECT — Cancel task
            </button>
          </div>
        </div>
      )}

      {/* Result */}
      {task?.result && task.status !== "hitl_pending" && (
        <div className="mb-4 bg-white/[0.02] border border-white/5 rounded-xl p-3 flex-shrink-0">
          <div className="flex items-center justify-between mb-2">
            <Chip label={task.status} />
            <div className="flex items-center gap-3 text-[10px] text-gray-600 font-mono">
              {task.routing && <span>→ {task.routing.agent?.slice(0,22)}</span>}
              {task.duration_ms && <span>{task.duration_ms}ms</span>}
            </div>
          </div>
          <div className="text-[11px] text-gray-400 font-mono leading-relaxed whitespace-pre-wrap">{task.result}</div>
        </div>
      )}

      {/* Input */}
      <div className="mt-auto space-y-2">
        <div className="flex gap-2">
          <input ref={inputRef}
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white font-mono focus:outline-none focus:border-purple-500/40 placeholder:text-gray-700"
            placeholder="analyze this contract for GDPR violations..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key==="Enter" && run()}
            disabled={loading}
          />
          <button onClick={() => run()} disabled={loading}
            className="text-xs bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-300 px-5 py-2.5 rounded-xl transition-colors font-bold">
            {loading ? <span className="animate-pulse">RUN</span> : "RUN ▶"}
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLES.slice(0,3).map(e => (
            <button key={e} onClick={() => run(e)} disabled={loading}
              className="text-[10px] text-gray-700 hover:text-gray-400 bg-white/[0.02] hover:bg-white/[0.04] border border-white/5 px-2 py-1 rounded-lg transition-colors font-mono text-left">
              {e.slice(0,40)}...
            </button>
          ))}
        </div>
      </div>
    </Panel>
  );
}

// ── Panel: SHA-256 Audit Chain ────────────────────────────────────────────────
function AuditPanel() {
  const [records, setRecords] = useState<Audit[]>([]);
  const [total, setTotal]     = useState(0);
  const [valid, setValid]     = useState<boolean|null>(null);
  const [verifying, setVerif] = useState(false);

  usePoll(() => {
    GET<{records:Audit[];total:number}>("/api/v1/audit/records?page_size=12")
      .then(d => { setRecords(d.records); setTotal(d.total); })
      .catch(() => {});
  }, 1500);

  const verify = async () => {
    setVerif(true);
    const r = await GET<{valid:boolean}>("/api/v1/audit/verify").catch(() => ({valid:false}));
    setValid(r.valid);
    setVerif(false);
    setTimeout(() => setValid(null), 5000);
  };

  const ACTION_STYLE: Record<string,{color:string;dot:string}> = {
    task_received:   {color:"text-blue-400",   dot:"bg-blue-500"},
    agent_routing:   {color:"text-teal-400",   dot:"bg-teal-500"},
    tool_call:       {color:"text-purple-400", dot:"bg-purple-500"},
    task_completed:  {color:"text-emerald-400",dot:"bg-emerald-500"},
    hitl_decision:   {color:"text-orange-400", dot:"bg-orange-500"},
    agent_registered:{color:"text-sky-400",    dot:"bg-sky-500"},
    system_started:  {color:"text-gray-400",   dot:"bg-gray-500"},
    system_stopped:  {color:"text-gray-400",   dot:"bg-gray-500"},
  };

  return (
    <Panel title="SHA-256 Audit Chain" sub="EU AI Act Article 9 — tamper-proof" accent="green"
      right={
        <div className="flex items-center gap-2">
          {valid !== null && (
            <span className={cx("text-[10px] font-mono font-bold", valid ? "text-emerald-400" : "text-red-400")}>
              {valid ? "✓ VALID" : "✗ BROKEN"}
            </span>
          )}
          <button onClick={verify} disabled={verifying}
            className="text-[10px] text-gray-600 hover:text-emerald-400 border border-white/8 hover:border-emerald-500/30 px-2.5 py-1 rounded-lg transition-colors font-mono">
            {verifying ? "..." : "VERIFY"}
          </button>
        </div>
      }>
      <div className="grid grid-cols-3 gap-2 mb-4">
        <StatCard label="Records" value={total} color="green" />
        <StatCard label="Algorithm" value="SHA-256" color="teal" />
        <StatCard label="Standard" value="Art.9" sub="EU AI Act" color="blue" />
      </div>

      <div className="flex-1 overflow-y-auto space-y-1 max-h-72">
        {records.length === 0 && (
          <div className="text-center py-8 text-gray-700 text-xs">
            No records yet — submit a task to see the chain grow
          </div>
        )}
        {records.map((r, i) => {
          const style = ACTION_STYLE[r.action] ?? {color:"text-gray-400",dot:"bg-gray-600"};
          return (
            <div key={r.id} className="flex items-start gap-2.5 group">
              <div className="flex flex-col items-center mt-1.5 flex-shrink-0 w-3">
                <div className={cx("w-2 h-2 rounded-full flex-shrink-0", style.dot)} />
                {i < records.length-1 && <div className="w-px flex-1 min-h-3 bg-white/5 mt-0.5" />}
              </div>
              <div className="flex-1 min-w-0 bg-white/[0.02] hover:bg-white/[0.04] rounded-xl px-3 py-2 transition-colors mb-0.5">
                <div className="flex items-center justify-between gap-2">
                  <span className={cx("text-[11px] font-mono font-medium", style.color)}>{r.action}</span>
                  <span className="text-[9px] text-gray-700 font-mono flex-shrink-0">{r.record_hash.slice(0,8)}…{r.record_hash.slice(-4)}</span>
                </div>
                {r.intent && <div className="text-[10px] text-gray-600 truncate mt-0.5">{r.intent}</div>}
                <div className="text-[9px] text-gray-800 font-mono mt-0.5">{r.agent_id.slice(0,30)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ── Panel: Performance ────────────────────────────────────────────────────────
function MetricsPanel() {
  const [m, setM] = useState<Metrics|null>(null);
  usePoll(() => GET<Metrics>("/api/v1/metrics").then(setM).catch(() => {}), 3000);

  const stack = [
    {name:"A2A Protocol v0.3", badge:"Linux Foundation · 150+ orgs", color:"text-blue-400",   bg:"bg-blue-500/8  border-blue-500/20"},
    {name:"LangGraph 0.2+",    badge:"State Machine · HITL · Checkpoint", color:"text-purple-400", bg:"bg-purple-500/8 border-purple-500/20"},
    {name:"MCP",               badge:"Model Context Protocol · Tools", color:"text-teal-400",  bg:"bg-teal-500/8  border-teal-500/20"},
    {name:"SHA-256 Audit",     badge:"EU AI Act Article 9 · Tamper-proof", color:"text-amber-400", bg:"bg-amber-500/8  border-amber-500/20"},
    {name:"Qdrant",            badge:"Vector DB · Semantic Routing", color:"text-pink-400",   bg:"bg-pink-500/8  border-pink-500/20"},
    {name:"sentence-tfm",      badge:"Local Embeddings · No API key", color:"text-green-400", bg:"bg-green-500/8  border-green-500/20"},
  ];

  return (
    <Panel title="Performance & Stack" sub="Production-grade metrics" accent="amber">
      {m && (
        <div className="grid grid-cols-2 gap-2 mb-4">
          <StatCard label="Completed" value={m.tasks_completed} color="green" />
          <StatCard label="Avg Route" value={`${Math.round(m.avg_routing_ms||0)}ms`} sub="target <500ms" color={m.avg_routing_ms < 500 ? "green" : "red"} />
          <StatCard label="HITL" value={m.hitl_triggered} sub="triggers" color="amber" />
          <StatCard label="Audit" value={m.audit_chain_length} sub="records" color="teal" />
        </div>
      )}
      <div className="space-y-1.5">
        {stack.map(s => (
          <div key={s.name} className={cx("flex items-center gap-2.5 rounded-xl px-3 py-2 border", s.bg)}>
            <div className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0" style={{color:s.color.replace("text-","").includes("-") ? undefined : undefined}} />
            <div className="min-w-0">
              <div className={cx("text-[11px] font-semibold font-mono", s.color)}>{s.name}</div>
              <div className="text-[9px] text-gray-600">{s.badge}</div>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ── Panel: Quick API Explorer ─────────────────────────────────────────────────
function ExplorerPanel() {
  const [result, setResult] = useState<string|null>(null);
  const [loading, setLoading] = useState<string|null>(null);

  const call = async (id:string, fn:()=>Promise<any>) => {
    setLoading(id); setResult(null);
    const r = await fn().catch(e => ({error: String(e)}));
    setResult(JSON.stringify(r, null, 2));
    setLoading(null);
  };

  const buttons = [
    {id:"card",  label:"Agent Card",      fn:() => GET("/.well-known/agent.json")},
    {id:"comp",  label:"Compliance",      fn:() => GET("/api/v1/audit/compliance")},
    {id:"route", label:"Route Test",      fn:() => POST("/api/v1/agents/route", {intent:"GDPR compliance document analysis"})},
    {id:"met",   label:"Metrics",         fn:() => GET("/api/v1/metrics")},
    {id:"docs",  label:"Swagger UI ↗",    fn:async() => { window.open(`${API}/docs`,"_blank"); return {opened:true}; }},
    {id:"qdrant",label:"Qdrant ↗",        fn:async() => { window.open("http://localhost:6333/dashboard","_blank"); return {opened:true}; }},
  ];

  return (
    <Panel title="API Explorer" sub="Test every endpoint in one click" accent="blue">
      <div className="grid grid-cols-2 gap-1.5 mb-3">
        {buttons.map(b => (
          <button key={b.id} onClick={() => call(b.id, b.fn)} disabled={loading !== null}
            className="text-[11px] bg-white/[0.03] hover:bg-white/[0.06] border border-white/8 hover:border-blue-500/30 text-gray-400 hover:text-white py-2 rounded-xl transition-all font-mono">
            {loading === b.id ? <span className="animate-pulse">...</span> : b.label}
          </button>
        ))}
      </div>
      {result && (
        <div className="bg-black/50 border border-white/5 rounded-xl p-3 font-mono text-[10px] text-gray-500 flex-1 overflow-y-auto max-h-48">
          {result}
        </div>
      )}
    </Panel>
  );
}

// ── App Shell ─────────────────────────────────────────────────────────────────
export default function App() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const timeStr = time.toLocaleTimeString("en", {hour12:false});
  const dateStr = time.toLocaleDateString("en", {month:"short", day:"numeric", year:"numeric"});

  return (
    <div className="min-h-screen text-white" style={{
      background: "#020204",
      backgroundImage: [
        "radial-gradient(ellipse 100% 60% at 15% 5%, rgba(59,130,246,0.07) 0%, transparent 55%)",
        "radial-gradient(ellipse 80% 50% at 85% 90%, rgba(20,184,166,0.05) 0%, transparent 55%)",
        "radial-gradient(ellipse 60% 40% at 50% 50%, rgba(124,58,237,0.03) 0%, transparent 60%)",
        "linear-gradient(rgba(255,255,255,0.012) 1px, transparent 1px)",
        "linear-gradient(90deg, rgba(255,255,255,0.012) 1px, transparent 1px)",
      ].join(","),
      backgroundSize: "cover, cover, cover, 48px 48px, 48px 48px",
    }}>

      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-black/50 backdrop-blur-xl">
        <div className="max-w-screen-xl mx-auto px-6 py-3 flex items-center justify-between">

          {/* Logo + brand */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5">
              <div className="relative flex-shrink-0">
                <svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <rect width="36" height="36" rx="10" fill="#0A0A0F"/>
                  {/* Outer ring */}
                  <circle cx="18" cy="18" r="13" stroke="#1E3A5F" strokeWidth="1"/>
                  {/* Orbit lines */}
                  <ellipse cx="18" cy="18" rx="13" ry="5" stroke="#1a4a7a" strokeWidth="0.6" strokeDasharray="2 2"/>
                  <ellipse cx="18" cy="18" rx="5" ry="13" stroke="#1a4a7a" strokeWidth="0.6" strokeDasharray="2 2"/>
                  {/* Core nodes — agents */}
                  <circle cx="18" cy="5"  r="2" fill="#3B8BD4"/>
                  <circle cx="29" cy="24" r="2" fill="#2DD4BF"/>
                  <circle cx="7"  cy="24" r="2" fill="#818CF8"/>
                  {/* Connection lines */}
                  <line x1="18" y1="7"  x2="27" y2="22" stroke="#3B8BD4" strokeWidth="0.8" strokeOpacity="0.6"/>
                  <line x1="27" y1="22" x2="9"  y2="22" stroke="#2DD4BF" strokeWidth="0.8" strokeOpacity="0.6"/>
                  <line x1="9"  y1="22" x2="18" y2="7"  stroke="#818CF8" strokeWidth="0.8" strokeOpacity="0.6"/>
                  {/* Central core */}
                  <circle cx="18" cy="18" r="3.5" fill="#0F172A" stroke="#3B8BD4" strokeWidth="1"/>
                  <circle cx="18" cy="18" r="1.5" fill="#3B8BD4"/>
                </svg>
              </div>
              <div>
                <div className="text-sm font-bold text-white tracking-tight">ATLAS</div>
                <div className="text-[9px] text-gray-600 font-mono tracking-widest">ORCHESTRATION PLATFORM</div>
              </div>
            </div>

            {/* Tech pills */}
            <div className="hidden lg:flex items-center gap-1">
              {[
                {label:"A2A v0.3", color:"text-blue-400 border-blue-500/25"},
                {label:"LangGraph", color:"text-purple-400 border-purple-500/25"},
                {label:"MCP", color:"text-teal-400 border-teal-500/25"},
                {label:"SHA-256", color:"text-amber-400 border-amber-500/25"},
                {label:"EU AI Act", color:"text-emerald-400 border-emerald-500/25"},
              ].map(p => (
                <span key={p.label} className={cx("text-[10px] font-mono px-2 py-0.5 rounded-md border", p.color)}>
                  {p.label}
                </span>
              ))}
            </div>
          </div>

          {/* Right: clock + links */}
          <div className="flex items-center gap-5">
            <div className="hidden md:flex items-center gap-1 text-[10px] font-mono">
              <span className="text-gray-600">{dateStr}</span>
              <span className="text-gray-400 ml-1 tabular-nums">{timeStr}</span>
            </div>
            <Glow color="green" />
            <span className="text-[10px] text-emerald-400 font-mono font-bold">LIVE</span>
            <div className="flex items-center gap-2 text-[10px] font-mono">
              <a href={`${API}/docs`} target="_blank"
                className="text-gray-600 hover:text-blue-400 border border-white/8 hover:border-blue-500/30 px-2.5 py-1.5 rounded-lg transition-colors">
                API DOCS ↗
              </a>
              <a href="https://github.com/achrafjarrou/atlas-orchestration" target="_blank"
                className="text-gray-600 hover:text-white border border-white/8 hover:border-white/20 px-2.5 py-1.5 rounded-lg transition-colors">
                GITHUB ↗
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Page title */}
      <div className="max-w-screen-xl mx-auto px-6 pt-8 pb-2">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white tracking-tight">
              AI Workstation <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-teal-400">2026</span>
            </h1>
            <p className="text-xs text-gray-600 mt-1.5 max-w-xl">
              The infrastructure layer that makes autonomous agents interoperable, auditable, and production-ready.
              Zero hardcoded rules · Cryptographic audit · Human oversight · $0/month infrastructure.
            </p>
          </div>
          <div className="hidden lg:flex items-center gap-2 text-[10px] text-gray-700 font-mono">
            <span className="text-gray-600">built by</span>
            <a href="https://github.com/achrafjarrou" target="_blank"
              className="text-blue-500 hover:text-blue-400 transition-colors">
              Achraf Jarrou
            </a>
          </div>
        </div>
      </div>

      {/* Dashboard grid */}
      <main className="max-w-screen-xl mx-auto px-6 py-5">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">

          {/* Row 1 */}
          <SystemPanel />
          <AgentPanel />
          <MetricsPanel />

          {/* Row 2 */}
          <div className="xl:col-span-2">
            <TaskPanel />
          </div>
          <AuditPanel />

          {/* Row 3 */}
          <div className="md:col-span-2 xl:col-span-3">
            <ExplorerPanel />
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-white/5 flex items-center justify-between text-[10px] text-gray-700 font-mono">
          <div className="flex items-center gap-4">
            <span>ATLAS v0.1.0</span>
            <span className="text-gray-800">·</span>
            <a href="https://github.com/achrafjarrou/atlas-orchestration" target="_blank"
              className="hover:text-gray-500 transition-colors">
              github.com/achrafjarrou/atlas-orchestration
            </a>
          </div>
          <div className="flex items-center gap-4">
            <a href={`${API}/.well-known/agent.json`} target="_blank" className="hover:text-gray-500 transition-colors">Agent Card</a>
            <a href="http://localhost:6333/dashboard"  target="_blank" className="hover:text-gray-500 transition-colors">Qdrant</a>
            <a href={`${API}/api/v1/audit/compliance`} target="_blank" className="hover:text-gray-500 transition-colors">Compliance</a>
            <span className="text-gray-800">·</span>
            <span>Achraf Jarrou · Casablanca 2026</span>
          </div>
        </div>
      </main>
    </div>
  );
}