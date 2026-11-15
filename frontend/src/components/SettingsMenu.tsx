/** Language and theme switcher, behind a single round button. */
import { IonIcon } from "@ionic/react";
import { close, moon, settingsOutline, sunny } from "ionicons/icons";
import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { LANGUAGES } from "../i18n";
import { setTheme, useTheme } from "../theme/theme";
import "./SettingsMenu.css";

export function SettingsMenu() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const current = i18n.resolvedLanguage ?? "es";

  // Close on Escape or when tapping elsewhere.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    const onPointer = (event: PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  return (
    <div className="de-settings" ref={wrapper}>
      <button
        type="button"
        className="de-icon-btn de-glass"
        aria-label={t("settings.open")}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <IonIcon icon={open ? close : settingsOutline} aria-hidden="true" />
      </button>
      {open && (
        <div id={panelId} className="de-settings__panel de-glass">
          <fieldset className="de-settings__group">
            <legend className="de-label">{t("settings.language")}</legend>
            <div className="de-segment">
              {LANGUAGES.map((language) => (
                <label key={language.code} className="de-segment__option">
                  <input
                    type="radio"
                    name="language"
                    checked={current === language.code}
                    onChange={() => void i18n.changeLanguage(language.code)}
                  />
                  <span lang={language.code}>{language.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="de-settings__group">
            <legend className="de-label">{t("settings.theme")}</legend>
            <div className="de-segment">
              {(["dark", "light"] as const).map((option) => (
                <label key={option} className="de-segment__option">
                  <input
                    type="radio"
                    name="theme"
                    checked={theme === option}
                    onChange={() => setTheme(option)}
                  />
                  <span>
                    <IonIcon icon={option === "dark" ? moon : sunny} aria-hidden="true" />
                    {t(`settings.${option}`)}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        </div>
      )}
    </div>
  );
}
