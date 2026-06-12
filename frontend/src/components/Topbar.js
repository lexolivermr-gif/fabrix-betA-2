import React from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LanguageSelector from "./LanguageSelector";

export default function Topbar({ title, subtitle, right }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <div className="topbar" data-testid="topbar">
      <div className="tb-title" data-testid="topbar-title">{title}</div>
      {subtitle && <div className="tb-sep" />}
      {subtitle && <div className="tb-sub" data-testid="topbar-subtitle">{subtitle}</div>}
      <div className="tb-right">
        <LanguageSelector />
        <div className="mbadge" data-testid="model-badge">
          <div className="dot" /> {t("badge")}
        </div>
        {right}
        <button className="btn bp bsm" onClick={() => navigate("/create")} data-testid="btn-new-manual">
          {t("nav.new")}
        </button>
      </div>
    </div>
  );
}
