/**
 * The runner's screen while sharing: own position, the link to send, and
 * honest warnings about what a web page can and cannot do with the GPS.
 */
import { IonAlert, IonContent, IonIcon, IonPage, IonSpinner, IonToast } from "@ionic/react";
import {
  cloudOfflineOutline,
  copyOutline,
  flaskOutline,
  locateOutline,
  logoWhatsapp,
  phonePortraitOutline,
  shareSocialOutline,
  sunnyOutline,
} from "ionicons/icons";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { SessionView } from "../api/types";
import { Brand } from "../components/Brand";
import { EtaHero } from "../components/EtaHero";
import { LiveMap } from "../components/LiveMap";
import { RemainingStats } from "../components/RemainingStats";
import { SettingsMenu } from "../components/SettingsMenu";
import { useElementSize } from "../components/useElementSize";
import { deriveStatus } from "../domain/status";
import { useNow } from "../live/useNow";
import { sessionStore, shareLink } from "../tracking/sessionStore";
import { useRunnerTracking } from "../tracking/useRunnerTracking";
import { useSheetPadding } from "./useSheetPadding";
import "./stage.css";

export function RunPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [session] = useState(() => sessionStore.load());
  const [own, setOwn] = useState<SessionView | null>(null);
  const [confirmStop, setConfirmStop] = useState(false);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);

  const [sheet, sheetSize] = useElementSize<HTMLElement>();
  const padding = useSheetPadding(sheetSize);
  const now = useNow();

  // Load the session once (route for the map; also proves it still exists).
  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    const load = () =>
      api
        .getOwnSession(session.id, session.runnerToken)
        .then((view) => !cancelled && setOwn(view))
        .catch((error) => {
          if (cancelled) return;
          if (error instanceof ApiError && error.status === 404) {
            sessionStore.clear(); // expired while we were away
            navigate("/", { replace: true });
          } else {
            window.setTimeout(load, 5000); // offline at start: keep trying
          }
        });
    void load();
    return () => {
      cancelled = true;
    };
  }, [session, navigate]);

  const active = own?.state === "active";
  const tracking = useRunnerTracking(
    session ?? { id: "", runnerToken: "", viewToken: "", shareUrl: "", demo: false },
    Boolean(session && active),
    own?.route?.points ?? null,
  );

  // The server is the authority on state (e.g. automatic arrival detection).
  const snapshot = tracking.snapshot ?? own;
  useEffect(() => {
    if (tracking.snapshot && own && tracking.snapshot.state !== own.state) {
      setOwn({ ...own, ...tracking.snapshot });
    }
  }, [tracking.snapshot, own]);

  useEffect(() => {
    if (tracking.gone) {
      sessionStore.clear();
      navigate("/", { replace: true });
    }
  }, [tracking.gone, navigate]);

  if (!session) return <Navigate to="/" replace />;

  if (!own || !snapshot) {
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

  const link = shareLink(session);
  const shareText = `${t("run.shareText")} ${link}`;
  const status = deriveStatus(snapshot, now);
  const finished = snapshot.state === "finished";
  // Show the phone's own fix immediately, even before the server confirms it.
  const position = tracking.lastFix ?? snapshot.position;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      window.prompt(t("run.copy"), link); // clipboard blocked: let them copy by hand
    }
  };

  const share = () => {
    navigator.share({ text: shareText }).catch(() => undefined); // user cancelled
  };

  const finish = async () => {
    setBusy(true);
    try {
      const result = await api.finish(session.id, session.runnerToken);
      setOwn({ ...own, ...result });
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await api.stop(session.id, session.runnerToken);
    } catch {
      /* offline: the session still expires by itself */
    }
    sessionStore.clear();
    navigate("/", { replace: true });
  };

  const startOver = () => {
    sessionStore.clear();
    navigate("/", { replace: true });
  };

  const gpsProblem =
    tracking.gps === "denied" || tracking.gps === "unavailable" || tracking.gps === "unsupported"
      ? tracking.gps
      : null;
  const gpsKey = { denied: "gpsDenied", unavailable: "gpsUnavailable", unsupported: "gpsUnsupported" };

  return (
    <IonPage>
      <IonContent scrollY={false}>
        <main className="de-stage">
          <LiveMap
            route={own.route?.points}
            progressM={snapshot.progress?.done_m}
            position={position}
            destination={snapshot.destination}
            markerTone={finished ? "done" : status === "stopped" ? "stopped" : "moving"}
            padding={padding}
            label={t("map.label")}
            recenterLabel={t("map.recenter")}
          />

          <header className="de-topbar">
            <div className="de-chip de-glass">
              <Brand compact />
              {!finished && (
                <span className="de-pill" data-status={tracking.gps === "ok" ? "moving" : "waiting"}>
                  <span className="de-pill__dot" aria-hidden="true" />
                  {t(tracking.gps === "ok" ? "run.live" : "run.gpsStarting")}
                </span>
              )}
            </div>
            <SettingsMenu />
          </header>

          <section className="de-sheet de-glass" ref={sheet}>
            {finished ? (
              <>
                <EtaHero snapshot={snapshot} status="finished" nowMs={now} own />
                <p className="de-muted">{t("run.finishedBody")}</p>
                <div className="de-sheet__actions">
                  <button type="button" className="de-btn de-btn--block" onClick={startOver}>
                    {t("run.newSession")}
                  </button>
                  <button
                    type="button"
                    className="de-btn de-btn--danger de-btn--block"
                    onClick={() => setConfirmStop(true)}
                  >
                    {t("run.stop")}
                  </button>
                </div>
              </>
            ) : (
              <>
                {gpsProblem && (
                  <div className="de-notice de-notice--danger" role="alert">
                    <IonIcon icon={locateOutline} aria-hidden="true" />
                    <span>
                      <strong>{t(`run.${gpsKey[gpsProblem]}Title`)}</strong>
                      {t(`run.${gpsKey[gpsProblem]}Body`)}
                    </span>
                  </div>
                )}

                <EtaHero snapshot={snapshot} status={status} nowMs={now} own />

                {snapshot.progress && (
                  <RemainingStats
                    progress={snapshot.progress}
                    showClimb={Boolean(own.route?.has_elevation)}
                  />
                )}

                <div className="de-sheet__actions" role="group" aria-labelledby="share-title">
                  <h2 className="de-sheet__title" id="share-title">
                    {t("run.shareTitle")}
                  </h2>
                  <a
                    className="de-btn de-btn--whatsapp de-btn--block"
                    href={`https://wa.me/?text=${encodeURIComponent(shareText)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <IonIcon icon={logoWhatsapp} aria-hidden="true" />
                    {t("run.shareWhatsapp")}
                  </a>
                  <div className={`de-sheet__actions${"share" in navigator ? " de-sheet__actions--row" : ""}`}>
                    {"share" in navigator && (
                      <button type="button" className="de-btn de-btn--ghost" onClick={share}>
                        <IonIcon icon={shareSocialOutline} aria-hidden="true" />
                        {t("run.share")}
                      </button>
                    )}
                    <button type="button" className="de-btn de-btn--ghost" onClick={copy}>
                      <IonIcon icon={copyOutline} aria-hidden="true" />
                      {t("run.copy")}
                    </button>
                  </div>
                </div>

                {session.demo ? (
                  <p className="de-notice">
                    <IonIcon icon={flaskOutline} aria-hidden="true" />
                    <span>{t("run.demoNotice")}</span>
                  </p>
                ) : (
                  <div className="de-notice de-notice--warn">
                    <IonIcon
                      icon={tracking.wakeLock === "active" ? sunnyOutline : phonePortraitOutline}
                      aria-hidden="true"
                    />
                    <span>
                      <strong>{t("run.screenTitle")}</strong>
                      {t("run.screenBody")}{" "}
                      {tracking.wakeLock === "active" && t("run.screenLocked")}
                      {tracking.wakeLock === "unsupported" && t("run.screenUnsupported")}
                    </span>
                  </div>
                )}

                {(!tracking.online || tracking.pending > 3) && (
                  <div className="de-notice" role="status">
                    <IonIcon icon={cloudOfflineOutline} aria-hidden="true" />
                    <span>
                      <strong>{t("run.bufferTitle")}</strong>
                      {t("run.bufferBody", { count: tracking.pending })}
                    </span>
                  </div>
                )}

                <div className="de-sheet__actions de-sheet__actions--row">
                  <button type="button" className="de-btn de-btn--ghost" disabled={busy} onClick={finish}>
                    {t("run.finish")}
                  </button>
                  <button
                    type="button"
                    className="de-btn de-btn--danger"
                    disabled={busy}
                    onClick={() => setConfirmStop(true)}
                  >
                    {t("run.stop")}
                  </button>
                </div>
              </>
            )}
          </section>
        </main>

        <IonAlert
          isOpen={confirmStop}
          header={t("run.stopConfirmTitle")}
          message={t("run.stopConfirmBody")}
          buttons={[
            { text: t("run.cancel"), role: "cancel" },
            { text: t("run.stopConfirmYes"), role: "destructive", handler: () => void stop() },
          ]}
          onDidDismiss={() => setConfirmStop(false)}
        />
        <IonToast
          isOpen={copied}
          message={t("run.copied")}
          duration={1800}
          position="top"
          onDidDismiss={() => setCopied(false)}
        />
      </IonContent>
    </IonPage>
  );
}
