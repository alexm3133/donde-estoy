/**
 * The hero: when does the runner arrive?
 *
 * One huge number, a plain-language sentence around it. This is what a
 * worried parent reads at arm's length, so it must be impossible to misread.
 */
import { useTranslation } from "react-i18next";
import type { Snapshot } from "../api/types";
import { durationParts, formatAgo, formatClock, wholeMinutes } from "../domain/format";
import {
  arrivalTimeMs,
  type LiveStatus,
  secondsSinceFix,
  secondsSinceMoved,
} from "../domain/status";
import "./EtaHero.css";

interface Props {
  snapshot: Snapshot;
  status: LiveStatus;
  /** Server-corrected current time (epoch ms). */
  nowMs: number;
  /** Runner's own screen: second person wording, smaller type. */
  own?: boolean;
}

export function EtaHero({ snapshot, status, nowMs, own = false }: Props) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const name = snapshot.runner_name;
  const who = own ? "own" : "other";

  if (status === "ended") {
    return (
      <div className="de-hero">
        <h1 className="de-hero__headline">{t(`hero.${who}.ended`, { name })}</h1>
        <p className="de-hero__sub">{t("hero.endedDetail")}</p>
      </div>
    );
  }

  if (status === "finished") {
    const at = snapshot.arrived_at ? formatClock(new Date(snapshot.arrived_at).getTime(), locale) : "";
    return (
      <div className="de-hero de-hero--arrived">
        <h1 className="de-hero__headline de-hero__headline--big">{t(`hero.${who}.arrived`, { name })}</h1>
        <p className="de-hero__sub">{t("hero.arrivedAt", { time: at })}</p>
      </div>
    );
  }

  const arrival = arrivalTimeMs(snapshot, status, nowMs);
  if (status === "waiting" || arrival === null) {
    return (
      <div className="de-hero">
        <h1 className="de-hero__headline">{t(`hero.${who}.waiting`, { name })}</h1>
        <p className="de-hero__sub">{t(`hero.${who}.waitingDetail`)}</p>
      </div>
    );
  }

  const secondsLeft = Math.max(0, (arrival - nowMs) / 1000);
  const { hours, minutes, imminent } = durationParts(secondsLeft);
  const clock = formatClock(arrival, locale);

  let detail: string;
  if (status === "stopped") {
    const stoppedFor = wholeMinutes(secondsSinceMoved(snapshot, nowMs) ?? 0);
    detail = t(`hero.${who}.stoppedDetail`, { minutes: stoppedFor, time: clock });
  } else if (status === "no_signal") {
    const ago = formatAgo(secondsSinceFix(snapshot, nowMs) ?? 0, locale);
    detail = t("hero.noSignalDetail", { ago });
  } else {
    detail = t("hero.around", { time: clock });
  }

  return (
    <div className={`de-hero${own ? " de-hero--compact" : ""}`}>
      <p className="de-hero__label">{t(`hero.${who}.arrivesIn`, { name })}</p>
      {/* Screen readers get one clean sentence instead of loose digits. */}
      <p className="de-visually-hidden" role="timer" aria-live="off">
        {imminent
          ? t("hero.imminent")
          : hours > 0
            ? t("hero.spokenHours", { hours, minutes })
            : t("hero.spokenMinutes", { minutes })}
        . {detail}
      </p>
      <p className="de-hero__value" aria-hidden="true">
        {imminent ? (
          <span className="de-hero__word">{t("hero.imminent")}</span>
        ) : (
          <>
            {hours > 0 && (
              <>
                <span className="de-hero__digits">{hours}</span>
                <span className="de-hero__unit">h</span>
              </>
            )}
            {/* Re-keyed each minute so the number "ticks" into place. */}
            <span className="de-hero__digits de-hero__digits--tick" key={minutes}>
              {hours > 0 ? String(minutes).padStart(2, "0") : minutes}
            </span>
            <span className="de-hero__unit">min</span>
          </>
        )}
      </p>
      <p className="de-hero__sub" aria-hidden="true">
        {detail}
      </p>
      {snapshot.eta?.confidence === "low" && status === "moving" && (
        <p className="de-hero__hint">{t("hero.lowConfidence")}</p>
      )}
    </div>
  );
}
