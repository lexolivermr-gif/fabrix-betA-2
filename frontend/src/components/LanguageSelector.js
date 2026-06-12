import React from "react";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGS } from "../lib/i18n";

export default function LanguageSelector() {
  const { i18n } = useTranslation();
  const current = SUPPORTED_LANGS.find((l) => i18n.language?.startsWith(l.code)) || SUPPORTED_LANGS[0];
  return (
    <select
      className="lang-sel"
      value={current.code}
      onChange={(e) => i18n.changeLanguage(e.target.value)}
      data-testid="language-selector"
      aria-label="Language"
      title="Language"
    >
      {SUPPORTED_LANGS.map((l) => (
        <option key={l.code} value={l.code}>{l.flag} {l.label}</option>
      ))}
    </select>
  );
}
