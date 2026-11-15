/**
 * Internationalisation: Spanish, Catalan and English.
 *
 * The language is detected from the browser and can be changed in the app
 * (remembered in localStorage). To add a language, copy `locales/en.json`,
 * translate it and register it in `LANGUAGES` below.
 */
import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";
import ca from "./locales/ca.json";
import en from "./locales/en.json";
import es from "./locales/es.json";

export const LANGUAGES = [
  { code: "es", label: "Español" },
  { code: "ca", label: "Català" },
  { code: "en", label: "English" },
] as const;

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { es: { translation: es }, ca: { translation: ca }, en: { translation: en } },
    fallbackLng: "es",
    supportedLngs: LANGUAGES.map((language) => language.code),
    nonExplicitSupportedLngs: true, // "ca-ES" -> "ca"
    interpolation: { escapeValue: false }, // React already escapes
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "de.lang",
      caches: ["localStorage"],
    },
  });

// Keep <html lang> in sync for screen readers and hyphenation.
const syncLang = (language: string) => {
  document.documentElement.lang = language.split("-")[0];
};
syncLang(i18n.resolvedLanguage ?? "es");
i18n.on("languageChanged", syncLang);

export default i18n;
