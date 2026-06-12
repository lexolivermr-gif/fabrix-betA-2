// i18n setup for Fabrix — 6 languages with browser detection + manual override.
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import fr from "./locales/fr.json";
import en from "./locales/en.json";
import es from "./locales/es.json";
import de from "./locales/de.json";
import pt from "./locales/pt.json";
import it from "./locales/it.json";

export const SUPPORTED_LANGS = [
  { code: "fr", label: "Français",  flag: "🇫🇷" },
  { code: "en", label: "English",   flag: "🇬🇧" },
  { code: "es", label: "Español",   flag: "🇪🇸" },
  { code: "de", label: "Deutsch",   flag: "🇩🇪" },
  { code: "pt", label: "Português", flag: "🇵🇹" },
  { code: "it", label: "Italiano",  flag: "🇮🇹" },
];

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: { translation: fr },
      en: { translation: en },
      es: { translation: es },
      de: { translation: de },
      pt: { translation: pt },
      it: { translation: it },
    },
    fallbackLng: "fr",
    supportedLngs: SUPPORTED_LANGS.map((l) => l.code),
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "fabrix_lang",
    },
  });

export default i18n;
