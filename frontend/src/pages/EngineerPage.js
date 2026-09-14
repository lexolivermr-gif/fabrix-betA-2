import React, { useState, useRef, useEffect } from "react";
import Topbar from "../components/Topbar";
import { api, API_BASE } from "../lib/apiClient";
import { toast } from "../lib/toastStore";

const LANGS = [
  { code: "en", label: "English" },
  { code: "fr", label: "Français" },
  { code: "es", label: "Español" },
  { code: "de", label: "Deutsch" },
  { code: "pt", label: "Português" },
  { code: "it", label: "Italiano" },
];

export default function EngineerPage() {
  const [project, setProject] = useState("");
  const [lang, setLang] = useState("en");
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [phase, setPhase] = useState("brief"); // brief | chat | building | done
  const [spec, setSpec] = useState(null);
  const [sheets, setSheets] = useState(null);
  const [status, setStatus] = useState(null);
  const chatRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [history, busy]);

  const start = async () => {
    if (project.trim().length < 8) { toast.warn("Describe the project in a bit more detail first."); return; }
    setPhase("chat"); setBusy(true);
    try {
      const { data } = await api.post("/engineer/ask", { project, history: [], lang });
      setHistory([{ role: "assistant", content: data.reply }]);
      setReady(!!data.ready);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "The engineer could not be reached.");
      setPhase("brief");
    } finally { setBusy(false); }
  };

  const send = async () => {
    const text = input.trim();
    if (!text) return;
    const next = [...history, { role: "user", content: text }];
    setHistory(next); setInput(""); setBusy(true);
    try {
      const { data } = await api.post("/engineer/ask", { project, history: next, lang });
      setHistory([...next, { role: "assistant", content: data.reply }]);
      setReady(!!data.ready);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "The engineer could not be reached.");
    } finally { setBusy(false); }
  };

  const build = async () => {
    setPhase("building");
    setStatus("The engineer is working out the mechanism…");
    try {
      const { data } = await api.post("/engineer/design", { project, history, lang });
      if (data?._validation?.errors?.length) {
        toast.warn(`Built with ${data._validation.errors.length} open issue(s) — see the console.`);
        console.warn("spec validation", data._validation);
      }
      setSpec(data);
      setStatus("Draughting the sheets…");
      const s = await api.post("/engineer/sheets", { spec: data });
      setSheets(s.data);
      setPhase("done");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Synthesis failed.");
      setPhase("chat");
    } finally { setStatus(null); }
  };

  const download = async () => {
    try {
      const r = await api.post("/engineer/pdf", { spec }, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = (sheets?.title || "fabrix-manual").replace(/[^a-z0-9]+/gi, "-").toLowerCase() + ".pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "PDF export failed.");
    }
  };

  return (
    <>
      <Topbar />
      <div className="pg" style={{ padding: 22, maxWidth: 1180, margin: "0 auto", width: "100%" }}>
        <div className="row" style={{ marginBottom: 14 }}>
          <div style={{ flex: 1 }}>
            <h1 style={{ fontFamily: "var(--font-title)", fontSize: 22, margin: 0 }}>Fabrix Engineer</h1>
            <div className="tb-sub">Ask questions first. Then every step, drawn.</div>
          </div>
          <select className="inp" style={{ width: 150 }} value={lang}
                  onChange={(e) => setLang(e.target.value)} data-testid="eng-lang">
            {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
        </div>

        {phase !== "done" && (
          <div className="card" style={{ padding: 18, marginBottom: 16 }}>
            <label className="tb-sub" style={{ display: "block", marginBottom: 6 }}>
              What should it build or upgrade?
            </label>
            <textarea
              className="inp" rows={3} data-testid="eng-project"
              placeholder="e.g. build a crossbow that can shoot toothpicks out of a single pine batten"
              value={project} onChange={(e) => setProject(e.target.value)}
              disabled={phase === "chat"} style={{ width: "100%", resize: "vertical" }}
            />
            {phase === "brief" && (
              <button className="btn bp" style={{ marginTop: 10 }} onClick={start} data-testid="eng-start">
                Ask the engineer
              </button>
            )}
          </div>
        )}

        {(phase === "chat" || phase === "building") && (
          <div className="card" style={{ padding: 0, overflow: "hidden", marginBottom: 16 }}>
            <div ref={chatRef} style={{ maxHeight: 340, overflowY: "auto", padding: 16 }}>
              {history.map((m, i) => (
                <div key={i} style={{
                  display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                  marginBottom: 10,
                }}>
                  <div style={{
                    maxWidth: "78%", padding: "10px 13px", borderRadius: 12, fontSize: 13.5,
                    lineHeight: 1.55, whiteSpace: "pre-wrap",
                    background: m.role === "user" ? "var(--violet)" : "var(--surface2)",
                    border: m.role === "user" ? "none" : "1px solid var(--border)",
                    borderBottomRightRadius: m.role === "user" ? 4 : 12,
                    borderBottomLeftRadius: m.role === "user" ? 12 : 4,
                  }}>{m.content}</div>
                </div>
              ))}
              {busy && <div className="tb-sub">Thinking…</div>}
              {status && <div className="tb-sub">{status}</div>}
            </div>
            <div className="row" style={{ padding: 12, borderTop: "1px solid var(--border)", gap: 8 }}>
              <input className="inp" style={{ flex: 1 }} data-testid="eng-input"
                     placeholder={ready ? "Add a last detail, or just build it…" : "Answer the engineer…"}
                     value={input} onChange={(e) => setInput(e.target.value)}
                     onKeyDown={(e) => e.key === "Enter" && !busy && send()} disabled={busy} />
              <button className="btn bg" onClick={send} disabled={busy || !input.trim()}>Send</button>
              <button className="btn bp" onClick={build} disabled={busy} data-testid="eng-build"
                      title={ready ? "" : "The engineer still has questions — you can build anyway"}>
                Build the guide
              </button>
            </div>
          </div>
        )}

        {phase === "done" && sheets && (
          <>
            <div className="row" style={{ marginBottom: 14 }}>
              <div style={{ flex: 1, fontFamily: "var(--font-title)", fontSize: 17 }}>{sheets.title}</div>
              <button className="btn bg bsm" onClick={() => { setPhase("chat"); setSpec(null); setSheets(null); }}>
                Back to questions
              </button>
              <button className="btn bp bsm" onClick={download} data-testid="eng-pdf">Download PDF</button>
            </div>

            {spec?.summary && <p className="tb-sub" style={{ marginTop: 0, marginBottom: 18, fontSize: 13 }}>{spec.summary}</p>}

            <div className="card" style={{ padding: 14, marginBottom: 16 }}>
              <div className="tb-sub" style={{ marginBottom: 8 }}>PARTS LIST</div>
              <div className="eg-sheet" dangerouslySetInnerHTML={{ __html: sheets.nomenclature }} />
            </div>

            {sheets.sheets.map((s, i) => {
              const st = spec?.steps?.[i] || {};
              return (
                <div className="card" key={s.n} style={{ padding: 14, marginBottom: 16 }}>
                  <div className="row" style={{ marginBottom: 8 }}>
                    <span className="tag" style={{ background: "rgba(124,92,191,.18)", color: "var(--violet-bright)" }}>
                      STEP {s.n}
                    </span>
                    <span style={{ fontFamily: "var(--font-title)", fontSize: 14.5 }}>{st.title || s.title}</span>
                    <span className="tb-sub" style={{ marginLeft: "auto" }}>{st.duration_min ? `${st.duration_min} min` : ""}</span>
                  </div>
                  <div className="eg-sheet" dangerouslySetInnerHTML={{ __html: s.svg }} />
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 12 }}>
                    <div>
                      <div className="tb-sub" style={{ marginBottom: 6 }}>DO</div>
                      <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.6 }}>
                        {(st.actions || []).map((a, j) => <li key={j} style={{ marginBottom: 4 }}>{a}</li>)}
                      </ol>
                    </div>
                    <div>
                      <div className="tb-sub" style={{ marginBottom: 6 }}>WHY IT WORKS</div>
                      <div style={{ fontSize: 13.5, lineHeight: 1.6, color: "var(--text2)" }}>{st.why}</div>
                      {st.check && (
                        <>
                          <div className="tb-sub" style={{ margin: "10px 0 6px" }}>CHECK</div>
                          <div style={{ fontSize: 13.5, lineHeight: 1.6, color: "var(--success)" }}>{st.check}</div>
                        </>
                      )}
                      {st.hazard && (
                        <div style={{ marginTop: 10, fontSize: 13, color: "var(--danger)" }}>⚠ {st.hazard}</div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {!!spec?.checks?.length && (
              <div className="card" style={{ padding: 14 }}>
                <div className="tb-sub" style={{ marginBottom: 8 }}>FINAL FUNCTION TEST</div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.6 }}>
                  {spec.checks.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
