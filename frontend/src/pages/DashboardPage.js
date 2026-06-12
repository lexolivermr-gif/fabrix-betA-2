import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/apiClient";
import Topbar from "../components/Topbar";
import { useAuth } from "../lib/authStore";
import { toast } from "../lib/toastStore";

function StatusBadge({ status }) {
  if (status === "complete") return <div className="cstat ok-s">Complet</div>;
  return <div className="cstat dr-s">{status}</div>;
}

export default function DashboardPage() {
  const user = useAuth((s) => s.user);
  const [usage, setUsage] = useState({ manuals_created: 0, images_generated: 0, pdfs_exported: 0 });
  const [manuals, setManuals] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const reload = async () => {
    try {
      const [u, m] = await Promise.all([api.get("/usage"), api.get("/manuals")]);
      setUsage(u.data);
      setManuals(m.data);
    } catch (e) { toast.error("Impossible de charger les manuels."); }
    finally { setLoading(false); }
  };

  useEffect(() => { reload(); }, []);

  const deleteManual = async (id, e) => {
    e?.stopPropagation?.();
    if (!window.confirm("Supprimer ce manuel ?")) return;
    try {
      await api.delete(`/manuals/${id}`);
      toast.success("Manuel supprimé.");
      reload();
    } catch { toast.error("Échec de la suppression."); }
  };

  const sharePublic = async (mn, e) => {
    e?.stopPropagation?.();
    try {
      if (!mn.is_public) {
        await api.patch(`/manuals/${mn.id}/public`, { is_public: true });
      }
      const url = `${window.location.origin}/share/${mn.id}`;
      await navigator.clipboard.writeText(url);
      toast.success("Lien copié !");
      reload();
    } catch { toast.error("Impossible de partager."); }
  };

  return (
    <>
      <Topbar title="Tableau de bord" subtitle={`Bienvenue, ${user?.name || user?.email?.split("@")[0]}`} />
      <div className="content" data-testid="dashboard-content">
        <div className="dgrid">
          <div className="sc" data-testid="stat-manuals">
            <span className="si">📋</span>
            <div className="sv">{usage.manuals_created}</div>
            <div className="sl">Manuels créés</div>
            <div className="st">{user?.plan === "pro" ? "Plan Pro" : `${user?.credits ?? 0} crédits restants`}</div>
          </div>
          <div className="sc" data-testid="stat-images">
            <span className="si">🖼️</span>
            <div className="sv">{usage.images_generated}</div>
            <div className="sl">Images générées</div>
          </div>
          <div className="sc" data-testid="stat-pdfs">
            <span className="si">📄</span>
            <div className="sv">{usage.pdfs_exported}</div>
            <div className="sl">PDFs exportés</div>
          </div>
        </div>

        <div className="sh">
          <div className="stitle">Mes manuels</div>
          <button className="btn bg bsm" onClick={reload} data-testid="btn-refresh">Rafraîchir</button>
        </div>

        {loading ? (
          <div className="gen"><div className="spinner" /><div className="sub">Chargement…</div></div>
        ) : manuals.length === 0 ? (
          <div className="empty" data-testid="empty-state">
            <h3>Aucun manuel pour l'instant</h3>
            <div>Crée ton premier manuel illustré en quelques minutes.</div>
            <div style={{ marginTop: 12 }}>
              <button className="btn bp" onClick={() => navigate("/create")} data-testid="btn-create-first">✨ Créer mon premier manuel</button>
            </div>
          </div>
        ) : (
          <div className="mgrid">
            {manuals.map((mn) => (
              <div
                key={mn.id}
                className="mc"
                onClick={() => navigate(`/manual/${mn.id}`)}
                data-testid={`manual-card-${mn.id}`}
              >
                <div className="ct">
                  {mn.cover_image_base64 ? (
                    <img src={`data:image/png;base64,${mn.cover_image_base64}`} alt="" />
                  ) : (
                    <div style={{ color: "#1a1a6e", fontFamily: "var(--font-mono)", fontSize: 12, padding: 20 }}>Pas d'aperçu</div>
                  )}
                  <div className="cto" />
                  <StatusBadge status={mn.status} />
                </div>
                <div className="cb">
                  <div className="ctitle">{mn.title}</div>
                  <div className="cmeta">
                    <span className="csteps">{mn.step_count} étapes</span>
                    <span style={{ color: "var(--border2)" }}>·</span>
                    <span>{mn.difficulty}</span>
                  </div>
                  <div className="cact">
                    <button className="btn bg bsm" onClick={(e) => sharePublic(mn, e)} data-testid={`btn-share-${mn.id}`}>🔗 Partager</button>
                    <button className="btn bg bsm tdgr" onClick={(e) => deleteManual(mn.id, e)} data-testid={`btn-delete-${mn.id}`}>Supprimer</button>
                  </div>
                </div>
              </div>
            ))}
            <div className="mcnew" onClick={() => navigate("/create")} data-testid="btn-new-manual-card">
              <div style={{ fontSize: 26, opacity: .6 }}>✨</div>
              <div style={{ fontSize: 13, fontWeight: 500 }}>Nouveau manuel</div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
