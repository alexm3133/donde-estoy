/**
 * The page behind a share link. No account, nothing to configure: a map and
 * one big answer to "when do they arrive?".
 */
import { IonContent, IonIcon, IonPage, IonSpinner } from "@ionic/react";
import { cloudOfflineOutline, notificationsOutline, warningOutline } from "ionicons/icons";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import type { Snapshot } from "../api/types";
import { AlertBanner } from "../components/AlertBanner";
import { Brand } from "../components/Brand";
import { ElevationProfile } from "../components/ElevationProfile";
import { EtaHero } from "../components/EtaHero";
import { LiveMap, type MarkerTone } from "../components/LiveMap";
import { RemainingStats } from "../components/RemainingStats";
import { SettingsMenu } from "../components/SettingsMenu";
import { StatusPill } from "../components/StatusPill";
import { useElementSize } from "../components/useElementSize";
import { type AlertKind, type AlertMemory, evaluateAlerts, NO_ALERTS } from "../domain/alerts";
import { durationParts, formatAgo, formatClock, wholeMinutes } from "../domain/format";
import {
  arrivalTimeMs,
  deriveStatus,
  type LiveStatus,
  secondsSinceFix,
  secondsSinceMoved,
} from "../domain/status";
import {
  enableNotifications,
  notificationPermission,
  type NotificationPermissionState,
  notify,
} from "../live/notifier";
import { useLiveSession } from "../live/useLiveSession";
import { useNow } from "../live/useNow";
import { useSheetPadding } from "./useSheetPadding";
import "./stage.css";

const TONES: Record<LiveStatus, MarkerTone> = {
  waiting: "lost",
  moving: "moving",
  stopped: "stopped",
  no_signal: "lost",
  finished: "done",
  ended: "lost",
};

/** Alerts already announced for a link survive a page reload. */
function loadMemory(token: string): AlertMemory {
  try {
    return { ...NO_ALERTS, ...JSON.parse(sessionStorage.getItem(`de.alerts.${token}`) ?? "{}") };
  } catch {
    return NO_ALERTS;
  }
}

export function ViewerPage() {
  const { token = "" } = useParams();
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const { link, view, clockOffsetMs } = useLiveSession(token);
  const nowMs = useNow() + clockOffsetMs;

  const [sheet, sheetSize] = useElementSize<HTMLElement>();
  const padding = useSheetPadding(sheetSize);

  const status = view ? deriveStatus(view, nowMs) : null;

  // ---- alerts -----------------------------------------------------------
  const memory = useRef<AlertMemory>(loadMemory(token));
  const [activeAlert, setActiveAlert] = useState<AlertKind | null>(null);
  const [permission, setPermission] = useState<NotificationPermissionState>(notificationPermission);

  const alertText = useMemo(
    () => (kind: AlertKind, snapshot: Snapshot, liveStatus: LiveStatus, now: number) => {
      const name = snapshot.runner_name;
      if (kind === "stalled") {
        const minutes = wholeMinutes(secondsSinceMoved(snapshot, now) ?? 0);
        const key = liveStatus === "no_signal" ? "stalledNoSignal" : "stalledStopped";
        return {
          title: t(`alerts.${key}.title`, { name, minutes }),
          body: t(`alerts.${key}.body`),
        };
      }
      const arrival = arrivalTimeMs(snapshot, liveStatus, now) ?? now;
      const time = formatClock(arrival, locale);
      if (kind === "arrived") {
        return { title: t("alerts.arrived.title", { name }), body: t("alerts.arrived.body", { time }) };
      }
      const minutes = Math.max(1, durationParts((arrival - now) / 1000).minutes);
      return {
        title: t("alerts.arrivingSoon.title", { name }),
        body: t("alerts.arrivingSoon.body", { minutes, time }),
      };
    },
    [t, locale],
  );

  useEffect(() => {
    if (!view || !status) return;
    const evaluation = evaluateAlerts(view, status, nowMs, memory.current);
    memory.current = evaluation.memory;
    sessionStorage.setItem(`de.alerts.${token}`, JSON.stringify(evaluation.memory));
    setActiveAlert(evaluation.active);
    for (const kind of evaluation.fire) {
      const { title, body } = alertText(kind, view, status, nowMs);
      void notify(title, body, kind === "stalled");
    }
  }, [view, status, nowMs, token, alertText]);

  // The browser tab tells the story too (useful when it is in the background).
  useEffect(() => {
    if (!view || !status) return;
    const arrival = arrivalTimeMs(view, status, nowMs);
    document.title =
      arrival !== null && status !== "finished"
        ? `${formatClock(arrival, locale)} · ${view.runner_name}`
        : `${view.runner_name} · ${t(`status.${status}`)}`;
  }, [view, status, nowMs, locale, t]);

  // ---- dead ends ----------------------------------------------------------
  if (link === "not_found" || (link === "error" && !view)) {
    const dead = link === "not_found";
    return (
      <IonPage>
        <IonContent scrollY={false}>
          <main className="de-message">
            <div className="de-message__card de-glass">
              <Brand />
              <h1>{t(dead ? "viewer.notFoundTitle" : "viewer.errorTitle")}</h1>
              <p>{t(dead ? "viewer.notFoundBody" : "viewer.errorBody")}</p>
              {dead ? (
                <Link className="de-btn de-btn--ghost" to="/">
                  {t("viewer.goHome")}
                </Link>
              ) : (
                <IonSpinner name="dots" aria-label={t("viewer.loading")} />
              )}
            </div>
          </main>
        </IonContent>
      </IonPage>
    );
  }

  if (!view || !status) {
    return (
      <IonPage>
        <IonContent scrollY={false}>
          <main className="de-message" aria-busy="true">
            <IonSpinner name="crescent" aria-label={t("viewer.loading")} />
          </main>
        </IonContent>
      </IonPage>
    );
  }

  const onTheWay = status === "moving" || status === "stopped" || status === "no_signal";
  const fixAge = secondsSinceFix(view, nowMs);
  const alert = activeAlert ? alertText(activeAlert, view, status, nowMs) : null;

  return (
    <IonPage>
      <IonContent scrollY={false}>
        <main className="de-stage">
          <LiveMap
            route={view.route?.points}
            progressM={view.progress?.done_m}
            track={view.track}
            position={view.position}
            destination={view.destination}
            markerTone={TONES[status]}
            padding={padding}
            label={t("map.label")}
            recenterLabel={t("map.recenter")}
          />

          <header className="de-topbar">
            <div className="de-chip de-glass">
              <Brand compact />
              <span className="de-chip__name">{view.runner_name}</span>
              <StatusPill status={status} />
            </div>
            <SettingsMenu />
          </header>

          <section className="de-sheet de-glass" ref={sheet} aria-live="polite">
            {alert && activeAlert && (
              <AlertBanner kind={activeAlert} title={alert.title} body={alert.body} />
            )}

            <EtaHero snapshot={view} status={status} nowMs={nowMs} />

            {onTheWay && view.progress && (
              <RemainingStats
                progress={view.progress}
                showClimb={Boolean(view.route?.has_elevation)}
              />
            )}

            {onTheWay && view.progress?.off_route && (
              <p className="de-notice de-notice--warn">
                <IonIcon icon={warningOutline} aria-hidden="true" />
                <span>{t("viewer.offRoute")}</span>
              </p>
            )}

            {view.route?.has_elevation && status !== "ended" && (
              <ElevationProfile
                route={view.route}
                progressM={status === "finished" ? view.route.distance_m : (view.progress?.done_m ?? null)}
              />
            )}

            {onTheWay && (
              <footer className="de-sheet__footer">
                <div className="de-sheet__meta">
                  <span>
                    {fixAge !== null && t("viewer.lastUpdate", { ago: formatAgo(fixAge, locale) })}
                  </span>
                  {link === "reconnecting" ? (
                    <span className="de-pill">
                      <IonIcon icon={cloudOfflineOutline} aria-hidden="true" />
                      {t("viewer.reconnecting")}
                    </span>
                  ) : permission === "default" ? (
                    <button
                      type="button"
                      className="de-btn de-btn--ghost de-btn--small"
                      onClick={async () => setPermission(await enableNotifications())}
                    >
                      <IonIcon icon={notificationsOutline} aria-hidden="true" />
                      {t("viewer.notifyEnable")}
                    </button>
                  ) : (
                    permission === "granted" && (
                      <span className="de-pill" data-status="moving">
                        <IonIcon icon={notificationsOutline} aria-hidden="true" />
                        {t("viewer.notifyOn")}
                      </span>
                    )
                  )}
                </div>
              </footer>
            )}
          </section>
        </main>
      </IonContent>
    </IonPage>
  );
}
