import React, { useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/apiClient";
import { toast } from "../lib/toastStore";
import { useAuth } from "../lib/authStore";

const PACKS = [
  { id: "5", credits: 5, price: "3,99" },
  { id: "15", credits: 15, price: "9,99" },
  { id: "40", credits: 40, price: "19,99" },
];

export default function CreditsPage() {
  const user = useAuth((s) => s.user);
  const [busy, setBusy] = useState(null);

  const buySub = async () => {
    setBusy("sub");
    try {
      const { data } = await api.post("/stripe/checkout/subscription");
      window.location.href = data.url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Stripe Checkout indisponible.");
    } finally { setBusy(null); }
  };

  const buyPack = async (pack) => {
    setBusy(pack);
    try {
      const { data } = await api.post("/stripe/checkout/credits", { pack });
      window.location.href = data.url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Stripe Checkout indisponible.");
    } finally { setBusy(null); }
  };

  return (
    <>
      <Topbar title="Crédits & Pro" subtitle="Choisis le plan qui correspond à tes besoins" />
      <div className="content">
        <div className="cgrid">
          <div className="pc" data-testid="plan-free">
            <div className="pname">Gratuit</div>
            <div style={{ fontSize: 13, color: "var(--text3)", marginBottom: 7 }}>Pour découvrir ManuelIA</div>
            <div className="pprice">0$ <span>/ mois</span></div>
            <ul className="pf">
              <li>3 crédits de bienvenue</li>
              <li>Jusqu'à 7 étapes par manuel</li>
              <li>Images GPT-4o incluses</li>
              <li>Export PDF standard</li>
            </ul>
            <button className="btn bg" style={{ width: "100%", justifyContent: "center" }} disabled>
              {user?.plan === "pro" ? "Plan secondaire" : "Plan actuel"}
            </button>
          </div>
          <div className="pc feat" data-testid="plan-pro">
            <div className="pbadge">Recommandé</div>
            <div className="pname">Pro</div>
            <div style={{ fontSize: 13, color: "var(--text3)", marginBottom: 7 }}>Pour les créateurs actifs</div>
            <div className="pprice">12$ <span>/ mois</span></div>
            <ul className="pf">
              <li>Manuels illimités</li>
              <li>Jusqu'à 20 étapes</li>
              <li>Régénération d'images à volonté</li>
              <li>Instructions personnalisées par image</li>
              <li>Partage public par lien</li>
              <li>PDF haute résolution</li>
            </ul>
            <button
              className="btn bp"
              style={{ width: "100%", justifyContent: "center", padding: 10 }}
              onClick={buySub}
              disabled={busy === "sub" || user?.plan === "pro"}
              data-testid="btn-buy-sub"
            >
              {user?.plan === "pro" ? "Abonné ✨" : (busy === "sub" ? "…" : "S'abonner — 12$/mois")}
            </button>
            <div className="stripebadge">🔒 <span className="mono" style={{ fontSize: 11 }}>Sécurisé par Stripe</span></div>
          </div>
        </div>
        <div style={{ maxWidth: 860, margin: "18px auto 0" }}>
          <div className="scard">
            <div className="scardtitle">🔄 Crédits ponctuels</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}>
              {PACKS.map((p) => (
                <div
                  key={p.id}
                  onClick={() => buyPack(p.id)}
                  data-testid={`pack-${p.id}`}
                  style={{
                    background: "var(--surface2)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--r)",
                    padding: 14,
                    textAlign: "center",
                    cursor: "pointer",
                    transition: "border-color .15s",
                  }}
                >
                  <div style={{ fontFamily: "var(--font-title)", fontSize: 22, fontWeight: 700, color: "var(--violet-bright)" }}>{p.credits}</div>
                  <div style={{ fontSize: 11, color: "var(--text3)", margin: "1px 0 7px" }}>crédits</div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{p.price}$</div>
                  {busy === p.id && <div style={{ fontSize: 11, marginTop: 4, color: "var(--text3)" }}>Redirection…</div>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
