import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Topbar from "../components/Topbar";
import { api } from "../lib/apiClient";
import { toast } from "../lib/toastStore";
import { useAuth } from "../lib/authStore";

export default function FixItPage() {
  const { t, i18n } = useTranslation();
  const refresh = useAuth((s) => s.refresh);
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState(null);
  const [job, setJob] = useState(null);
  const [manualId, setManualId] = useState(null);

  const onFileChange = (f) => {
    setFile(null);
    setPreview(null);
    if (!f) return;
    if (!/^image\/(jpeg|png|webp)$/.test(f.type)) {
      toast.error("JPG, PNG ou WEBP requis.");
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      toast.error("Photo trop volumineuse (max 10 Mo).");
      return;
    }
    setFile(f);
    const r = new FileReader();
    r.onload = (e) => setPreview(e.target.result);
    r.readAsDataURL(f);
  };

  const submit = async () => {
    if (!file) { toast.warn(t("fixit.upload")); return; }
    setBusy(true);
    setRefusal(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (description) fd.append("description", description);
      fd.append("lang", (i18n.language || "fr").slice(0, 2));
      const { data } = await api.post("/fixit/generate", fd, { headers: { "Content-Type": "multipart/form-data" } });
      if (data.refusal) {
        setRefusal(data.reason);
      } else {
        const jobId = data.job_id;
        pollJob(jobId);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Échec de la génération Fix-It.");
    } finally { setBusy(false); }
  };

  const pollJob = (jid) => {
    const tick = async () => {
      try {
        const { data } = await api.get(`/manuals/jobs/${jid}`);
        setJob(data);
        if (data.state === "done") {
          setManualId(data.manual_id);
          await refresh();
        } else if (data.state === "error") {
          toast.error(data.error || "Génération en erreur.");
        } else {
          setTimeout(tick, 2000);
        }
      } catch { setTimeout(tick, 3000); }
    };
    tick();
  };

  return (
    <>
      <Topbar title={t("fixit.title")} subtitle={t("fixit.sub")} />
      <div className="content">
        <div className="wcon" data-testid="fixit-page">
          {!job && (
            <div className="wpanel">
              <h2 className="wptitle">{t("fixit.title")}</h2>
              <p className="wpsub">{t("fixit.sub")}</p>
              <label
                style={{
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                  border: "2px dashed var(--border2)", borderRadius: "var(--r)", padding: 28, cursor: "pointer",
                  background: preview ? "#fff" : "var(--surface2)", minHeight: 220, marginBottom: 14,
                }}
              >
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => onFileChange(e.target.files?.[0])}
                  style={{ display: "none" }}
                  data-testid="input-photo"
                />
                {preview ? (
                  <img src={preview} alt="preview" style={{ maxHeight: 220, maxWidth: "100%", objectFit: "contain" }} />
                ) : (
                  <>
                    <div style={{ fontSize: 32, opacity: .5 }}>📷</div>
                    <div style={{ marginTop: 6, color: "var(--text2)" }}>{t("fixit.upload")}</div>
                    <div style={{ marginTop: 4, fontSize: 11, color: "var(--text3)" }}>{t("fixit.upload_hint")}</div>
                  </>
                )}
              </label>
              <div className="fg">
                <label className="fl">{t("fixit.description")}</label>
                <textarea
                  className="inp" rows={3}
                  value={description} onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("fixit.description_placeholder")}
                  data-testid="input-fixit-desc"
                />
              </div>
              {refusal && (
                <div className="stips" style={{ marginBottom: 10 }}>
                  <strong>{t("fixit.refused_title")}</strong>
                  <span>{refusal}</span>
                </div>
              )}
              <div className="wact">
                <span />
                <button className="btn bp" onClick={submit} disabled={!file || busy} data-testid="btn-fixit-submit">
                  {busy ? "…" : t("fixit.analyze")}
                </button>
              </div>
            </div>
          )}

          {job && !manualId && (
            <div className="wpanel gen" data-testid="fixit-progress">
              <div className="spinner" />
              <div className="ttl">{t("wizard.gen_title")}</div>
              <div className="sub">{job?.status_text || t("common.loading")}</div>
              <div className="pb"><div className="pf2" style={{ width: `${job?.progress ?? 5}%` }} /></div>
              <div className="lbl">{job?.label}</div>
              {Array.isArray(job?.steps_status) && job.steps_status.length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "center", marginTop: 14 }}>
                  {job.steps_status.map((s) => (
                    <span key={s.idx} className={`tag ${s.state === "done" ? "tv" : "tg"}`}>
                      {s.state === "done" ? "✓" : s.state === "running" ? "•••" : "…"} {s.idx + 1}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {manualId && (
            <div className="wpanel" data-testid="fixit-done">
              <h2 className="wptitle">{t("wizard.review_title")}</h2>
              <p className="wpsub">{t("wizard.review_sub")}</p>
              <div className="wact">
                <button className="btn bg" onClick={() => navigate("/")}>{t("common.back")}</button>
                <button className="btn bp" onClick={() => navigate(`/manual/${manualId}`)}>{t("wizard.open_manual")}</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
