import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { ask, report, searchDevices } from "./api";
import type { AskResult, Device } from "./types";
import "./style.css";

const CODES: Record<string, string> = { "": "All codes", DQA: "DQA pulse oximeter", NBW: "NBW glucose meter",
  FRN: "FRN infusion pump", DXN: "DXN blood pressure", DRX: "DRX ECG electrode" };

function DeviceSearch() {
  const [q, setQ] = useState(""); const [code, setCode] = useState("DQA");
  const [rows, setRows] = useState<Device[]>([]); const [err, setErr] = useState("");
  const run = async () => { setErr(""); try { setRows(await searchDevices(q, code)); } catch (e) { setErr(String(e)); } };
  const download = async (k: string) => {
    const md = await report(k);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" })); a.download = `${k}-predicate-draft.md`; a.click();
  };
  return (
    <section>
      <h2>1 · Find cleared devices</h2>
      <div className="row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="device or company name" onKeyDown={(e) => e.key === "Enter" && run()} />
        <select value={code} onChange={(e) => setCode(e.target.value)}>
          {Object.entries(CODES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <button onClick={run}>Search</button>
      </div>
      {err && <p className="err">{err}</p>}
      {rows.length > 0 && (
        <table><thead><tr><th>K-number</th><th>Device</th><th>Applicant</th><th>Cleared</th><th></th></tr></thead>
          <tbody>{rows.map((d) => (
            <tr key={d.k_number}>
              <td><a href={d.source} target="_blank" rel="noreferrer">{d.k_number}</a></td>
              <td>{d.device_name}</td><td>{d.applicant}</td><td>{d.decision_date}</td>
              <td><button className="small" onClick={() => download(d.k_number)}>Draft table</button></td>
            </tr>))}</tbody></table>)}
    </section>
  );
}

function Ask() {
  const [q, setQ] = useState("How quickly does FDA tell a sponsor whether a 510(k) is administratively complete?");
  const [res, setRes] = useState<AskResult | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const run = async () => { setBusy(true); setErr(""); try { setRes(await ask(q)); } catch (e) { setErr(String(e)); } finally { setBusy(false); } };
  return (
    <section>
      <h2>2 · Ask the FDA guidance</h2>
      <div className="row">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && run()} />
        <button onClick={run} disabled={busy}>{busy ? "…" : "Ask"}</button>
      </div>
      {err && <p className="err">{err}</p>}
      {res && (
        <div className="answer">
          {res.found ? <p>{res.answer}</p> : <p className="muted">No verified answer in the guidance. Passages below.</p>}
          {res.note && <p className="muted">{res.note}</p>}
          {res.citations.map((c, i) => (
            <blockquote key={i}>“{c.quote}”<cite>{c.doc_title}, page {c.page}</cite></blockquote>))}
          <p className="muted">Route: {res.route.map((s) => `${s.model} ${s.verified ? "✓ quotes verified" : "✗ " + s.problems.join(", ")}`).join(" → ") || "none"}</p>
          <details><summary>Retrieved passages ({res.passages.length})</summary>
            {res.passages.map((p) => <p key={p.id} className="passage"><b>{p.doc_title}, p. {p.page}</b> {p.text}</p>)}
          </details>
        </div>)}
    </section>
  );
}

function App() {
  return (
    <main>
      <h1>Medical Device 510(k) Research Assistant</h1>
      <p className="muted">Public openFDA 510(k) data + FDA guidance. Research aid only: every answer quotes its source page, and a person checks it before use.</p>
      <DeviceSearch />
      <Ask />
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
