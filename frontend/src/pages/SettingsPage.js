import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Topbar from "../components/Topbar";
import { useAuth } from "../lib/authStore";
import { api } from "../lib/apiClient";
import { toast } from "../lib/toastStore";

export default function SettingsPage() {
  const user = useAuth((s) => s.user);
  const updatePrefs = useAuth((s) => s.updatePrefs);
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();
  const [name, setName] = useState(user?.name || "");
  const [savingName, setSavingName] = useState(false);

  const onTogglePrefs = async (field, value) => {
    try {
      await updatePrefs({ [field]: value });
      toast.success("Préférence enregistrée.");
    } catch { toast.error("Échec."); }
  };

  const saveName = async () => {
    setSavingName(true);
    try {
      await updatePrefs({ name });
      toast.success("Profil mis à jour.");
    } catch { toast.error("Échec."); }
    finally { setSavingName(false); }
  };

  const deleteAll = async () => {
    if (!window.confirm("Supprimer TOUS tes manuels ? Cette action est irréversible.")) return;
    try {
      const { data } = await api.delete("/manuals");
      toast.success(`${data.deleted} manuel(s) supprimé(s).`);
    } catch { toast.error("Échec de la suppression."); }
  };

  const deleteAccount = async () => {
    if (!window.confirm("Supprimer définitivement ton compte ?")) return;
    if (!window.confirm("Es-tu absolument sûr ? Toutes tes données seront perdues.")) return;
    try {
      await api.delete("/auth/me");
      toast.success("Compte supprimé.");
      logout();
      navigate("/auth");
    } catch { toast.error("Échec de la suppression."); }
  };

  return (
    <>
      <Topbar title="Paramètres" subtitle="Profil, modèle IA et préférences" />
      <div className="content">
        <div className="ssec" data-testid="settings-content">
          <div className="scard">
            <div className="scardtitle">👤 Profil</div>
            <div className="srow">
              <span className="sk">Nom</span>
              <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input className="inp" style={{ width: 180, padding: "6px 10px", fontSize: 12 }} value={name} onChange={(e) => setName(e.target.value)} data-testid="input-settings-name" />
                <button className="btn bg bsm" onClick={saveName} disabled={savingName} data-testid="btn-save-name">Enregistrer</button>
              </span>
            </div>
            <div className="srow"><span className="sk">Courriel</span><span className="sv2">{user?.email}</span></div>
            <div className="srow"><span className="sk">Plan</span><span className="sv2">{user?.plan === "pro" ? "Pro ✨" : "Gratuit"}</span></div>
            <div className="srow"><span className="sk">Crédits</span><span className="sv2">{user?.plan === "pro" ? "∞" : user?.credits}</span></div>
            <div className="srow"><span className="sk">Membre depuis</span><span className="sv2">{user?.created_at?.slice(0, 10)}</span></div>
          </div>

          <div className="scard">
            <div className="scardtitle">🤖 Pipeline IA (3 couches anti-hallucination)</div>
            <div className="srow"><span className="sk">Texte (chat + étapes)</span><span className="sv2">gpt-4o</span></div>
            <div className="srow"><span className="sk">Prompt builder image</span><span className="sv2">gpt-4o (conversationnel)</span></div>
            <div className="srow"><span className="sk">Génération image</span><span className="sv2">gpt-image-2</span></div>
            <div className="srow"><span className="sk">Validation visuelle</span><span className="sv2">gpt-4o vision</span></div>
            <div className="srow"><span className="sk">Résolution images</span><span className="sv2">1536×1024 · haute qualité</span></div>
            <div className="srow"><span className="sk">Style visuel</span><span className="sv2">IKEA #0058A3 · #CC0008</span></div>
            <div className="srow"><span className="sk">Étapes par manuel</span><span className="sv2">10 à 15</span></div>
            <div className="srow"><span className="sk">Tentatives max par image</span><span className="sv2">3 (1 + 2 retries)</span></div>
            <div style={{ background: "rgba(107,203,160,.08)", border: "1px solid rgba(107,203,160,.25)", borderRadius: "var(--rs)", padding: "11px 13px", marginTop: 10, fontSize: 12, color: "var(--success)", lineHeight: 1.55 }} data-testid="shared-context-badge">
              <strong>✓ 3 couches de cohérence visuelle :</strong><br />
              ① <strong>Style anchor texte</strong> commun à toutes les étapes<br />
              ② <strong>Image de référence</strong> (étape 1) passée à toutes les étapes suivantes via gpt-image-2 img2img<br />
              ③ <strong>Validation GPT-4o vision</strong> avec régénération automatique si non conforme
            </div>
          </div>

          <div className="scard">
            <div className="scardtitle">⚙ Préférences</div>
            <div className="srow">
              <span className="sk">Notifications par email</span>
              <label className="tog" data-testid="toggle-emails">
                <input type="checkbox" checked={!!user?.email_notifications} onChange={(e) => onTogglePrefs("email_notifications", e.target.checked)} data-testid="toggle-emails-input" />
                <div className="togtr" />
              </label>
            </div>
            <div className="srow">
              <span className="sk">Manuels publics par défaut</span>
              <label className="tog" data-testid="toggle-public">
                <input type="checkbox" checked={!!user?.public_by_default} onChange={(e) => onTogglePrefs("public_by_default", e.target.checked)} data-testid="toggle-public-input" />
                <div className="togtr" />
              </label>
            </div>
          </div>

          <div className="scard">
            <div className="scardtitle">🔴 Zone de danger</div>
            <div className="srow">
              <span className="sk tdgr">Supprimer tous mes manuels</span>
              <button className="btn bg bsm tdgr" onClick={deleteAll} data-testid="btn-delete-all-manuals">Supprimer</button>
            </div>
            <div className="srow">
              <span className="sk tdgr">Supprimer mon compte</span>
              <button className="btn bg bsm tdgr" onClick={deleteAccount} data-testid="btn-delete-account">Supprimer</button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
