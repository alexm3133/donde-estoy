/**
 * Runner set-up: who you are, where you are going, then one big button.
 */
import { IonContent, IonIcon, IonPage, IonSpinner } from "@ionic/react";
import {
  alertCircleOutline,
  cloudUploadOutline,
  locateOutline,
  lockClosedOutline,
  logoGithub,
  playOutline,
} from "ionicons/icons";
import { type FormEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Activity, LatLon, ParsedRoute, SessionCreate } from "../api/types";
import { Brand } from "../components/Brand";
import { ElevationProfile } from "../components/ElevationProfile";
import { LiveMap } from "../components/LiveMap";
import { MountainBackdrop } from "../components/MountainBackdrop";
import { SettingsMenu } from "../components/SettingsMenu";
import { DEMO_ROUTE } from "../demo/demoRoute";
import { formatClimb, formatDistance } from "../domain/format";
import { sessionStore } from "../tracking/sessionStore";
import "./HomePage.css";

type DestinationMode = "gpx" | "point";
const REPO_URL = "https://github.com/alexm3133/donde-estoy";

export function HomePage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const navigate = useNavigate();

  const [name, setName] = useState(() => sessionStore.loadName());
  const [activity, setActivity] = useState<Activity>("run");
  const [mode, setMode] = useState<DestinationMode>("gpx");
  const [route, setRoute] = useState<ParsedRoute | null>(null);
  const [point, setPoint] = useState<LatLon | null>(null);
  const [myPosition, setMyPosition] = useState<LatLon | null>(null);
  const [stallMinutes, setStallMinutes] = useState(10);
  const [parsing, setParsing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  // An outing is already being shared from this device: go back to it.
  if (sessionStore.load()) return <Navigate to="/run" replace />;

  const errorText = (code: string) =>
    t(`home.errors.${code}`, { defaultValue: t("home.errors.generic") });

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    setParsing(true);
    try {
      setRoute(await api.parseGpx(file));
    } catch (problem) {
      setRoute(null);
      setError(errorText(problem instanceof ApiError ? problem.code : "generic"));
    } finally {
      setParsing(false);
      if (fileInput.current) fileInput.current.value = ""; // allow re-picking the same file
    }
  };

  const locateMe = () => {
    setError(null);
    navigator.geolocation?.getCurrentPosition(
      (position) =>
        setMyPosition({ lat: position.coords.latitude, lon: position.coords.longitude }),
      () => setError(errorText("location")),
      { enableHighAccuracy: true, timeout: 15_000 },
    );
  };

  const start = async (body: SessionCreate, demo: boolean) => {
    setError(null);
    setSubmitting(true);
    try {
      const created = await api.createSession(body);
      sessionStore.clear(); // drop leftovers (e.g. unsent buffer) of older outings
      sessionStore.saveName(body.runner_name);
      sessionStore.save({
        id: created.id,
        runnerToken: created.runner_token,
        viewToken: created.view_token,
        shareUrl: created.share_url,
        demo,
      });
      navigate("/run");
    } catch (problem) {
      setError(errorText(problem instanceof ApiError ? problem.code : "generic"));
      setSubmitting(false);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const runnerName = name.trim();
    if (!runnerName) return setError(errorText("nameRequired"));
    const destination =
      mode === "gpx" ? route && { route_points: route.raw_points } : point && { destination: point };
    if (!destination) return setError(errorText("destinationRequired"));
    void start(
      { runner_name: runnerName, activity, stall_alert_minutes: stallMinutes, ...destination },
      false,
    );
  };

  const startDemo = () =>
    void start(
      {
        runner_name: name.trim() || "Alex",
        activity: "run",
        stall_alert_minutes: stallMinutes,
        route_points: DEMO_ROUTE,
      },
      true,
    );

  return (
    <IonPage className="de-home">
      <MountainBackdrop />
      <IonContent>
        <div className="de-home__inner">
          <header className="de-home__top">
            <Brand />
            <SettingsMenu />
          </header>

          <main>
            <section className="de-home__intro">
              <h1>{t("home.title")}</h1>
              <p>{t("home.subtitle")}</p>
            </section>

            <form className="de-home__form de-glass" onSubmit={onSubmit} noValidate>
              <div className="de-field">
                <label className="de-label" htmlFor="runner-name">
                  {t("home.name")}
                </label>
                <input
                  id="runner-name"
                  className="de-input"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder={t("home.namePlaceholder")}
                  maxLength={40}
                  autoComplete="given-name"
                  enterKeyHint="done"
                />
              </div>

              <fieldset className="de-field de-fieldset">
                <legend className="de-label">{t("home.activity")}</legend>
                <div className="de-segment">
                  {(["run", "hike"] as const).map((option) => (
                    <label key={option} className="de-segment__option">
                      <input
                        type="radio"
                        name="activity"
                        checked={activity === option}
                        onChange={() => setActivity(option)}
                      />
                      <span>{t(`home.${option}`)}</span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <fieldset className="de-field de-fieldset">
                <legend className="de-label">{t("home.destination")}</legend>
                <div className="de-segment">
                  {(["gpx", "point"] as const).map((option) => (
                    <label key={option} className="de-segment__option">
                      <input
                        type="radio"
                        name="destination-mode"
                        checked={mode === option}
                        onChange={() => setMode(option)}
                      />
                      <span>{t(option === "gpx" ? "home.destGpx" : "home.destPoint")}</span>
                    </label>
                  ))}
                </div>

                {mode === "gpx" ? (
                  <div className="de-home__destination">
                    <input
                      ref={fileInput}
                      type="file"
                      accept=".gpx,application/gpx+xml,application/xml,text/xml"
                      className="de-visually-hidden"
                      tabIndex={-1}
                      aria-hidden="true"
                      onChange={(event) => void onFile(event.target.files?.[0])}
                    />
                    {route && (
                      <>
                        <div className="de-home__map">
                          <LiveMap
                            route={route.points}
                            destination={{
                              lat: route.points[route.points.length - 1][0],
                              lon: route.points[route.points.length - 1][1],
                            }}
                            label={t("map.label")}
                            recenterLabel={t("map.recenter")}
                          />
                        </div>
                        {route.has_elevation && <ElevationProfile route={route} progressM={null} />}
                        <p className="de-home__summary">
                          {route.name && <strong>{route.name}</strong>}
                          {t(route.has_elevation ? "home.routeSummary" : "home.routeNoElevation", {
                            distance: formatDistance(route.distance_m, locale),
                            ascent: formatClimb(route.ascent_m, locale),
                            descent: formatClimb(route.descent_m, locale),
                          })}
                        </p>
                      </>
                    )}
                    <button
                      type="button"
                      className="de-btn de-btn--ghost de-btn--block"
                      onClick={() => fileInput.current?.click()}
                      disabled={parsing}
                    >
                      {parsing ? (
                        <IonSpinner name="dots" aria-hidden="true" />
                      ) : (
                        <IonIcon icon={cloudUploadOutline} aria-hidden="true" />
                      )}
                      {t(parsing ? "home.gpxParsing" : route ? "home.gpxChange" : "home.gpxChoose")}
                    </button>
                    {!route && <p className="de-home__hint">{t("home.gpxHint")}</p>}
                  </div>
                ) : (
                  <div className="de-home__destination">
                    <div className="de-home__map de-home__map--tall">
                      <LiveMap
                        position={myPosition}
                        destination={point}
                        onPick={setPoint}
                        markerTone="stopped"
                        label={t("map.pickerLabel")}
                        recenterLabel={t("map.recenter")}
                      />
                    </div>
                    <p className="de-home__hint" role="status">
                      {t(point ? "home.pointSet" : "home.pointHint")}
                    </p>
                    <button type="button" className="de-btn de-btn--ghost de-btn--block" onClick={locateMe}>
                      <IonIcon icon={locateOutline} aria-hidden="true" />
                      {t("home.locateMe")}
                    </button>
                  </div>
                )}
              </fieldset>

              <div className="de-field">
                <label className="de-label" htmlFor="stall-minutes">
                  {t("home.stall")}
                </label>
                <p className="de-home__range-value">{t("home.stallValue", { minutes: stallMinutes })}</p>
                <input
                  id="stall-minutes"
                  type="range"
                  className="de-range"
                  min={5}
                  max={60}
                  step={5}
                  value={stallMinutes}
                  onChange={(event) => setStallMinutes(Number(event.target.value))}
                  aria-valuetext={t("home.stallValue", { minutes: stallMinutes })}
                />
              </div>

              {error && (
                <p className="de-notice de-notice--danger" role="alert">
                  <IonIcon icon={alertCircleOutline} aria-hidden="true" />
                  <span>{error}</span>
                </p>
              )}

              <button type="submit" className="de-btn de-btn--large de-btn--block" disabled={submitting}>
                {t(submitting ? "home.starting" : "home.start")}
              </button>

              <p className="de-home__privacy">
                <IonIcon icon={lockClosedOutline} aria-hidden="true" />
                <span>{t("home.privacy")}</span>
              </p>
            </form>

            <section className="de-home__demo">
              <button type="button" className="de-btn de-btn--ghost" onClick={startDemo} disabled={submitting}>
                <IonIcon icon={playOutline} aria-hidden="true" />
                {t("home.demo")}
              </button>
              <p>{t("home.demoHint")}</p>
            </section>
          </main>

          <footer className="de-home__footer">
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
              <IonIcon icon={logoGithub} aria-hidden="true" />
              {t("home.openSource")}
            </a>
          </footer>
        </div>
      </IonContent>
    </IonPage>
  );
}
