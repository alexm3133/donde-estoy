import { useTranslation } from "react-i18next";
import type { LiveStatus } from "../domain/status";
import "./StatusPill.css";

/** Small coloured label: moving / stopped / no signal / arrived… */
export function StatusPill({ status }: { status: LiveStatus }) {
  const { t } = useTranslation();
  return (
    <span className="de-pill" data-status={status}>
      <span className="de-pill__dot" aria-hidden="true" />
      {t(`status.${status}`)}
    </span>
  );
}
