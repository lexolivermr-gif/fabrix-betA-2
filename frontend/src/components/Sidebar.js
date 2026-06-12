import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/authStore";

export default function Sidebar() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();

  const items = [
    { to: "/",        label: t("nav.dashboard"), ico: "▣" },
    { to: "/create",  label: t("nav.create"),    ico: "✨" },
    { to: "/fixit",   label: t("nav.fixit"),     ico: "🔧" },
    { to: "/credits", label: t("nav.credits"),   ico: "✎" },
    { to: "/settings",label: t("nav.settings"),  ico: "⚙" },
  ];

  return (
    <aside className="sb" data-testid="sidebar">
      <div className="sb-logo"><span className="dot-vi" /> Fabrix</div>
      <nav className="sb-nav">
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            end={it.to === "/"}
            className={({ isActive }) => `sb-link${isActive ? " active" : ""}`}
            data-testid={`nav-${it.to.replace("/", "") || "home"}`}
          >
            <span className="ico">{it.ico}</span>
            {it.label}
          </NavLink>
        ))}
      </nav>
      <div className="sb-foot">
        <div className="sb-creds">
          <span className="lbl">{t("common.optional") && "Credits"}</span>
          <span className="val" data-testid="sidebar-credits">{user?.plan === "pro" ? "∞" : (user?.credits ?? 0)}</span>
        </div>
        <div className="sb-user" onClick={() => navigate("/settings")} data-testid="sidebar-user">
          <div className="sb-av">{(user?.name || user?.email || "?").slice(0, 1).toUpperCase()}</div>
          <div className="sb-user-info">
            <span className="sb-user-name">{user?.name || "User"}</span>
            <span className="sb-user-mail">{user?.email}</span>
          </div>
        </div>
        <button
          className="btn bg bsm"
          style={{ width: "100%", marginTop: 8, justifyContent: "center" }}
          onClick={() => { logout(); navigate("/auth"); }}
          data-testid="btn-logout"
        >
          {t("nav.logout")}
        </button>
      </div>
    </aside>
  );
}
