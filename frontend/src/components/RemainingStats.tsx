import { IonIcon } from "@ionic/react";
import { arrowDown, arrowUp, flagOutline } from "ionicons/icons";
import { useTranslation } from "react-i18next";
import type { Progress } from "../api/types";
import { formatClimb, formatDistance } from "../domain/format";
import "./RemainingStats.css";

interface Props {
  progress: Progress;
  /** Whether ascent/descent are known (routes with elevation data). */
  showClimb: boolean;
}

/** What is left: distance, and climb/descent when the route knows them. */
export function RemainingStats({ progress, showClimb }: Props) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  return (
    <dl className="de-stats">
      <div className="de-stats__item">
        <dt>
          <IonIcon icon={flagOutline} aria-hidden="true" />
          {t(showClimb || progress.total_m !== null ? "stats.distanceLeft" : "stats.distanceLeftApprox")}
        </dt>
        <dd>{formatDistance(progress.remaining_m, locale)}</dd>
      </div>
      {showClimb && (
        <>
          <div className="de-stats__item">
            <dt>
              <IonIcon icon={arrowUp} aria-hidden="true" />
              {t("stats.ascentLeft")}
            </dt>
            <dd>{formatClimb(progress.remaining_ascent_m, locale)}</dd>
          </div>
          <div className="de-stats__item">
            <dt>
              <IonIcon icon={arrowDown} aria-hidden="true" />
              {t("stats.descentLeft")}
            </dt>
            <dd>{formatClimb(progress.remaining_descent_m, locale)}</dd>
          </div>
        </>
      )}
    </dl>
  );
}
