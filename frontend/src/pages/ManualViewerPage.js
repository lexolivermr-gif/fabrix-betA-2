import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Topbar from "../components/Topbar";
import { api, API_BASE } from "../lib/apiClient";
import { toast } from "../lib/toastStore";

const SUGGESTIONS = ["vue de dessus", "zoom mains", "vue éclatée", "focus boulons", "sans personnage"];

export default function ManualViewerPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [manual, setManual] = useState(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [regenOpen, setRegenOpen] = useState(false);
  const [regenText, setRegenText] = useState("");
  const [regenBusy, setRegenBusy] = useState(false);

  const [allJobId, setAllJobId] = useState(null);
  const [allJob, setAllJob] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/manuals/${id}`);
      setManual(data);
    } catch (e) {
      toast.error("Manuel introuvable.");
      navigate("/");
    }
  }, [id, navigate]);

  useEffect(() => { load(); }, [load]);

  if (!manual) {
    return (
      <>
        <Topbar title="Manuel" subtitle="Chargement…" />
        <div className="content"><div className="gen"><div className="spinner" /><div className="sub">Chargement…</div></div></div>
      </>
    );
  }

  const step = manual.steps[activeIdx];

  const regen = async () => {
    setRegenBusy(true);
    try {
      await api.post(`/manuals/${id}/steps/${step.id}/regen`, {
        custom_instructions: regenText.trim() || null,
      });
      toast.success("Image régénérée.");
      setRegenText("");
      setRegenOpen(false);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Échec de la régénération.");
    } finally {
      setRegenBusy(false);
    }
  };

  const regenAll = async () => {
    if (!window.confirm(`Régénérer les ${manual.steps.length} images ? Cela peut prendre quelques minutes.`)) return;
    try {
      const { data } = await api.post(`/manuals/${id}/regen-all`);
      setAllJobId(data.job_id);
      toast.info("Régénération en cours…");
      pollAll(data.job_id);
    } catch (e) {
      toast.error("Impossible de lancer la régénération globale.");
    }
  };

  const pollAll = (jid) => {
    const tick = async () => {
      try {
        const { data } = await api.get(`/manuals/jobs/${jid}`);
        setAllJob(data);
        if (data.state === "done") {
          toast.success("Toutes les images ont été régénérées ✨");
          setAllJobId(null);
          setAllJob(null);
          await load();
          return;
        }
        if (data.state === "error") {
          toast.error(data.error || "Échec.");
          setAllJobId(null);
          setAllJob(null);
          return;
        }
        setTimeout(tick, 1500);
      } catch (e) { setTimeout(tick, 2500); }
    };
    tick();
  };

  const sharePublic = async () => {
    try {
      if (!manual.is_public) {
        await api.patch(`/manuals/${id}/public`, { is_public: true });
        setManual({ ...manual, is_public: true });
      }
      const url = `${window.location.origin}/share/${id}`;
      await navigator.clipboard.writeText(url);
      toast.success("Lien copié !");
    } catch {
      toast.error("Impossible de partager.");
    }
  };

  const exportPdf = async () => {
    if (!manual.pdf_unlocked) {
      // Try to unlock — for V1 the owner can self-unlock (pricing logic TBD).
      try {
        await api.patch(`/manuals/${id}/pdf-unlock`);
        toast.success("PDF déverrouillé.");
        setManual({ ...manual, pdf_unlocked: true });
      } catch (e) {
        toast.error("Ce manuel n'est pas encore déverrouillé pour l'export PDF.");
        return;
      }
    }
    try {
      const token = localStorage.getItem("manuelia_token");
      const res = await fetch(`${API_BASE}/manuals/${id}/export/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fabrix-${manual.title.replace(/\s+/g, "_")}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("PDF téléchargé.");
    } catch (e) { toast.error("Échec export PDF."); }
  };

  return (
    <>
      <Topbar title="Visionneuse" subtitle={manual.title} />
      <div className="content" data-testid="viewer-content">
        <div className="rabar">
          <div style={{ fontSize: 13, color: "var(--text2)" }}>
            🖼️ <strong style={{ color: "var(--text)" }}>{manual.title}</strong>
            {" · "}
            <span style={{ fontSize: 12, color: "var(--text3)" }}>
              {manual.steps.length} étapes · {manual.difficulty} · {manual.total_duration_min} min
            </span>
          </div>
          <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
            <button className="btn bg bsm" onClick={regenAll} disabled={!!allJobId} data-testid="btn-regen-all">↺ Régénérer tout</button>
            <button className="btn bg bsm" onClick={sharePublic} data-testid="btn-share">🔗 Partager</button>
            <button className="btn bp bsm" onClick={exportPdf} data-testid="btn-export-pdf">⬇ Exporter PDF</button>
          </div>
        </div>

        {allJob && (
          <div className="regen-all-bar" data-testid="regen-all-progress">
            <div className="lbl">{allJob.label}</div>
            <div style={{ flex: 1 }}>
              <div className="pb" style={{ margin: 0 }}><div className="pf2" style={{ width: `${allJob.progress}%` }} /></div>
            </div>
            <div className="lbl">{allJob.progress}%</div>
          </div>
        )}

        <div className="vlayout">
          <div className="vsidebar">
            <div className="vstitle">Étapes du manuel</div>
            {manual.steps.map((s, i) => (
              <div
                key={s.id}
                className={`sth ${i === activeIdx ? "active" : ""}`}
                onClick={() => { setActiveIdx(i); setRegenOpen(false); }}
                data-testid={`step-list-${i+1}`}
              >
                <div className="sthn">{i + 1}</div>
                <div className="stht">{s.title}</div>
                <div className="sthc">{s.image_base64 ? "✓" : "…"}</div>
              </div>
            ))}
          </div>

          <div className="vmain">
            <div className="steph">
              <div>
                <div className="stepn">Étape {activeIdx + 1} / {manual.steps.length}</div>
                <div className="steptit" data-testid="step-title">{step.title}</div>
              </div>
              <div style={{ display: "flex", gap: 5 }}>
                <span className="tag tv">{manual.difficulty}</span>
                <span className="tag tg">{step.duration_min} min</span>
              </div>
            </div>

            <div className="imgcon">
              {step.image_base64 ? (
                <img src={`data:image/png;base64,${step.image_base64}`} alt={step.title} data-testid="step-image" />
              ) : (
                <div className="skel" />
              )}
              <div className="iact">
                <button
                  className="btn bg bsm bico"
                  title="Personnaliser et régénérer"
                  onClick={() => setRegenOpen((v) => !v)}
                  data-testid="btn-toggle-regen"
                >↺</button>
              </div>
            </div>

            {regenOpen && (
              <div className="rp" data-testid="regen-panel">
                <div className="rlabel">Instructions à DALL-E 3 (optionnel)</div>
                <div className="rrow">
                  <input
                    type="text"
                    className="inp"
                    value={regenText}
                    onChange={(e) => setRegenText(e.target.value)}
                    placeholder='Ex: "vue de dessus", "zoom sur les boulons", "montrer les deux mains"…'
                    onKeyDown={(e) => { if (e.key === "Enter") regen(); }}
                    data-testid="input-regen"
                  />
                  <button className="btn bp" onClick={regen} disabled={regenBusy} data-testid="btn-regen">
                    {regenBusy ? "…" : "↺ Régénérer"}
                  </button>
                </div>
                <div className="rhint">Suggestions :
                  {SUGGESTIONS.map((s) => (
                    <span key={s} onClick={() => setRegenText(s)} data-testid={`suggestion-${s.replace(/\s+/g, '-')}`}>{s}</span>
                  ))}
                </div>
              </div>
            )}

            <p className="sdesc" data-testid="step-desc">{step.description}</p>
            {step.tip && (
              <div className="stips"><strong>💡 Conseil GPT-4o</strong>{step.tip}</div>
            )}

            <div className="snav">
              <button className="btn bg" onClick={() => setActiveIdx((i) => Math.max(0, i - 1))} disabled={activeIdx === 0} data-testid="btn-prev-step">← Précédent</button>
              <span style={{ fontSize: 12, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>
                {activeIdx + 1} / {manual.steps.length}
              </span>
              <button className="btn bp" onClick={() => setActiveIdx((i) => Math.min(manual.steps.length - 1, i + 1))} disabled={activeIdx === manual.steps.length - 1} data-testid="btn-next-step">Suivant →</button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
