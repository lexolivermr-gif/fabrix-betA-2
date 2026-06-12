import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/authStore";
import { toast } from "../lib/toastStore";

export default function AuthPage() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("test@manuelia.com");
  const [password, setPassword] = useState("Test1234!");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const login = useAuth((s) => s.login);
  const signup = useAuth((s) => s.signup);
  const navigate = useNavigate();
  const loc = useLocation();
  const params = new URLSearchParams(loc.search);
  const next = params.get("next") || "/";

  const submit = async (e) => {
    e?.preventDefault?.();
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
        toast.success("Bienvenue !");
      } else {
        await signup(email.trim(), password, name.trim() || undefined);
        toast.success("Compte créé ✨");
      }
      navigate(next, { replace: true });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erreur d'authentification.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen" data-testid="auth-screen">
      <div className="amb amb1" />
      <div className="amb amb2" />
      <form className="acard" onSubmit={submit}>
        <div className="alogo">ManuelIA</div>
        <p className="atagline">
          Manuels illustrés étape par étape.<br />
          Texte <strong style={{ color: "var(--text2)" }}>ET</strong> images générés par GPT-4o.
        </p>

        {mode === "signup" && (
          <div className="fg">
            <label className="fl">Nom</label>
            <input className="inp" value={name} onChange={(e) => setName(e.target.value)} placeholder="Olivié" data-testid="input-name" />
          </div>
        )}
        <div className="fg">
          <label className="fl">Adresse courriel</label>
          <input className="inp" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="vous@exemple.com" data-testid="input-email" required />
        </div>
        <div className="fg">
          <label className="fl">Mot de passe</label>
          <input className="inp" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" data-testid="input-password" required />
        </div>

        <button
          className="btn bp"
          type="submit"
          style={{ width: "100%", justifyContent: "center", padding: 10, marginBottom: 4 }}
          disabled={busy}
          data-testid="btn-submit"
        >
          {busy ? "…" : mode === "login" ? "Connexion" : "Créer mon compte"}
        </button>

        <p className="alink">
          {mode === "login" ? (
            <>Pas de compte ?{" "}
              <a onClick={() => setMode("signup")} data-testid="link-switch">Créer un compte gratuit</a>
            </>
          ) : (
            <>Déjà inscrit ?{" "}
              <a onClick={() => setMode("login")} data-testid="link-switch">Se connecter</a>
            </>
          )}
        </p>
      </form>
    </div>
  );
}
