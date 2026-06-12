import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Topbar from "../components/Topbar";
import { api } from "../lib/apiClient";
import { toast } from "../lib/toastStore";
import { useAuth } from "../lib/authStore";

export default function CreatePage() {
  const { t, i18n } = useTranslation();
  const [stepIdx, setStepIdx] = useState(0);
  const [project, setProject] = useState("");
  const [history, setHistory] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);

  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [manualId, setManualId] = useState(null);

  const refresh = useAuth((s) => s.refresh);
  const navigate = useNavigate();
  const chatRef = useRef(null);

  const lang = (i18n.language || "fr").slice(0, 2);

  const STEPS = [t("wizard.steps.project"), t("wizard.steps.clarify"), t("wizard.steps.gen"), t("wizard.steps.review")];

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [history]);

  const goClarify = async () => {
    if (!project.trim() || project.trim().length < 8) {
      toast.warn(t("wizard.project_placeholder"));
      return;
    }
    setStepIdx(1);
    setChatBusy(true);
    try {
      const { data } = await api.post("/ai/clarify", { project, history: [], lang });
      setHistory([{ role: "assistant", content: data.reply }]);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Chat failed.");
      setStepIdx(0);
    } finally { setChatBusy(false); }
  };

  const sendUserMsg = async () => {
    const text = chatInput.trim();
    if (!text) return;
    const newHist = [...history, { role: "user", content: text }];
    setHistory(newHist);
    setChatInput("");
    setChatBusy(true);
    try {
      const { data } = await api.post("/ai/clarify", { project, history: newHist, lang });
      setHistory([...newHist, { role: "assistant", content: data.reply }]);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Chat failed.");
    } finally { setChatBusy(false); }
  };

  const startGeneration = async () => {
    setStepIdx(2);
    try {
      const { data } = await api.post("/manuals/generate", { project, history, lang });
      setJobId(data.job_id);
      pollJob(data.job_id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Cannot start.");
      setStepIdx(1);
    }
  };

  const pollJob = async (jid) => {
    const tick = async () => {
      try {
        const { data } = await api.get(`/manuals/jobs/${jid}`);
        setJob(data);
        if (data.state === "done") {
          setManualId(data.manual_id);
          await refresh();
          setStepIdx(3);
        } else if (data.state === "error") {
          toast.error(data.error || "Generation error.");
          setStepIdx(1);
        } else {
          setTimeout(tick, 2000);
        }
      } catch { setTimeout(tick, 3000); }
    };
    tick();
  };

  return (
    <>
      <Topbar title={t("nav.create")} subtitle={`${t("wizard.steps.project")} ${stepIdx + 1}/${STEPS.length}`} />
      <div className="content">
        <div className="wcon" data-testid="wizard">
          <div className="wsteps">
            {STEPS.map((label, i) => {
              const state = i < stepIdx ? "done" : i === stepIdx ? "active" : "";
              return (
                <div key={label} className={`ws ${state}`} data-testid={`step-${i+1}`}>
                  <div className="wnum">{i < stepIdx ? "✓" : i + 1}</div>
                  <div className="wlabel">{label}</div>
                </div>
              );
            })}
          </div>

          {stepIdx === 0 && (
            <div className="wpanel" data-testid="wizard-step-1">
              <h2 className="wptitle">{t("wizard.project_title")}</h2>
              <p className="wpsub">{t("wizard.project_sub")}</p>
              <div className="mcallout">🤖 &nbsp;<div><strong>Claude Sonnet 4.5</strong> + <strong>gpt-image-2</strong></div></div>
              <div className="fg">
                <label className="fl">{t("wizard.project_title")}</label>
                <textarea
                  className="inp" rows={4}
                  value={project} onChange={(e) => setProject(e.target.value)}
                  placeholder={t("wizard.project_placeholder")}
                  data-testid="input-project"
                />
              </div>
              <div className="wact">
                <span />
                <button className="btn bp" onClick={goClarify} disabled={chatBusy} data-testid="btn-next-to-clarify">
                  {STEPS[1]} →
                </button>
              </div>
            </div>
          )}

          {stepIdx === 1 && (
            <div className="wpanel" data-testid="wizard-step-2">
              <h2 className="wptitle">{t("wizard.clarify_title")}</h2>
              <p className="wpsub">{t("wizard.clarify_sub")}</p>
              <div className="chat-area" ref={chatRef} data-testid="chat-area">
                <div className="cmsg user">
                  <div className="cav user">U</div>
                  <div className="cbub">{project}</div>
                </div>
                {history.map((m, i) => (
                  <div key={i} className={`cmsg ${m.role === "assistant" ? "ai" : "user"}`}>
                    <div className={`cav ${m.role === "assistant" ? "ai" : "user"}`}>{m.role === "assistant" ? "C" : "U"}</div>
                    <div className="cbub">{m.content}</div>
                  </div>
                ))}
                {chatBusy && <div className="cmsg ai"><div className="cav ai">C</div><div className="cbub">…</div></div>}
              </div>
              <div className="cinrow">
                <textarea
                  className="inp" rows={1}
                  value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendUserMsg(); }}}
                  placeholder={t("wizard.chat_placeholder")}
                  disabled={chatBusy}
                  data-testid="input-chat"
                />
                <button className="btn bp" onClick={sendUserMsg} disabled={chatBusy} data-testid="btn-chat-send">{t("common.send")}</button>
              </div>
              <div className="wact">
                <button className="btn bg" onClick={() => setStepIdx(0)} data-testid="btn-back-to-project">{t("common.back")}</button>
                {(() => {
                  const userAnswers = history.filter((m) => m.role === "user").length;
                  const enough = userAnswers >= 3;
                  return (
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 12, color: enough ? "var(--success)" : "var(--text3)", fontFamily: "var(--font-mono)" }}>
                        {t("wizard.answers_count", { n: userAnswers })} {enough ? "✓" : t("wizard.answers_min")}
                      </span>
                      <button className="btn bp" onClick={startGeneration} disabled={!enough || chatBusy} data-testid="btn-generate">
                        {t("wizard.go_generate")}
                      </button>
                    </div>
                  );
                })()}
              </div>
            </div>
          )}

          {stepIdx === 2 && (
            <div className="wpanel gen" data-testid="wizard-step-3">
              <div className="spinner" />
              <div className="ttl">{t("wizard.gen_title")}</div>
              <div className="sub" data-testid="gen-status">{job?.status_text || t("common.loading")}</div>
              <div className="pb"><div className="pf2" style={{ width: `${job?.progress ?? 5}%` }} /></div>
              <div className="lbl" data-testid="gen-label">{job?.label || "…"}</div>

              {Array.isArray(job?.steps_status) && job.steps_status.length > 0 && (
                <div className="step-grid" data-testid="step-grid">
                  {job.steps_status.map((s) => (
                    <span key={s.idx} className={`step-pill ${s.state || ""}`} data-testid={`step-pill-${s.idx + 1}`}>
                      {s.state === "done" ? "✓" : s.state === "running" ? "•••" : s.state === "error" ? "✗" : "·"}
                      <span> {s.idx + 1}</span>
                    </span>
                  ))}
                </div>
              )}

              <div style={{ marginTop: 14, fontSize: 11.5, color: "var(--text3)", lineHeight: 1.6 }}>
                {t("wizard.gen_pipeline")}<br />{t("wizard.gen_closeok")}
              </div>
            </div>
          )}

          {stepIdx === 3 && (
            <div className="wpanel" data-testid="wizard-step-4">
              <h2 className="wptitle">{t("wizard.review_title")}</h2>
              <p className="wpsub">{t("wizard.review_sub")}</p>
              <div className="wact">
                <button className="btn bg" onClick={() => navigate("/")} data-testid="btn-back-dashboard">{t("common.back")}</button>
                <button className="btn bp" onClick={() => navigate(`/manual/${manualId}`)} data-testid="btn-open-manual">{t("wizard.open_manual")}</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
