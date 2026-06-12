import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/apiClient";

export default function PublicSharePage() {
  const { id } = useParams();
  const [manual, setManual] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/manuals/${id}/public`);
        setManual(data);
      } catch (e) {
        setError(e?.response?.data?.detail || "Manuel introuvable ou non public.");
      }
    })();
  }, [id]);

  if (error) {
    return (
      <div className="share-wrap">
        <div className="amb amb1" />
        <div className="amb amb2" />
        <div className="empty"><h3>Impossible d'afficher ce manuel</h3><div>{error}</div></div>
      </div>
    );
  }
  if (!manual) {
    return (
      <div className="share-wrap">
        <div className="amb amb1" />
        <div className="amb amb2" />
        <div className="gen"><div className="spinner" /><div className="sub">Chargement…</div></div>
      </div>
    );
  }

  return (
    <div className="share-wrap" data-testid="public-share">
      <div className="amb amb1" />
      <div className="amb amb2" />
      <div className="share-head">
        <div>
          <div className="share-title" data-testid="share-title">{manual.title}</div>
          <div style={{ fontSize: 13, color: "var(--text3)", marginTop: 4 }}>
            {manual.steps.length} étapes · {manual.difficulty} · {manual.total_duration_min} min
          </div>
        </div>
        <div className="mbadge"><div className="dot" /> GPT-4o + DALL-E 3</div>
      </div>

      {manual.cover_image_base64 && (
        <div className="imgcon" style={{ marginBottom: 18 }}>
          <img src={`data:image/png;base64,${manual.cover_image_base64}`} alt="cover" />
        </div>
      )}

      {manual.steps.map((step, i) => (
        <div key={step.id} className="vmain" style={{ marginBottom: 16 }} data-testid={`share-step-${i + 1}`}>
          <div className="steph">
            <div>
              <div className="stepn">Étape {i + 1} / {manual.steps.length}</div>
              <div className="steptit">{step.title}</div>
            </div>
            <div style={{ display: "flex", gap: 5 }}>
              <span className="tag tg">{step.duration_min} min</span>
            </div>
          </div>
          <div className="imgcon">
            {step.image_base64 ? (
              <img src={`data:image/png;base64,${step.image_base64}`} alt={step.title} />
            ) : (
              <div className="skel" />
            )}
          </div>
          <p className="sdesc">{step.description}</p>
          {step.tip && <div className="stips"><strong>💡 Conseil</strong>{step.tip}</div>}
        </div>
      ))}

      <div className="share-foot">
        Généré par <strong style={{ color: "var(--violet-bright)" }}>ManuelIA</strong> — GPT-4o + DALL-E 3
      </div>
    </div>
  );
}
