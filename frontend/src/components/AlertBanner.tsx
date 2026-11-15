import { IonIcon } from "@ionic/react";
import { checkmarkCircle, time, warning } from "ionicons/icons";
import type { AlertKind } from "../domain/alerts";
import "./AlertBanner.css";

const ICONS: Record<AlertKind, string> = {
  arriving_soon: time,
  arrived: checkmarkCircle,
  stalled: warning,
};

interface Props {
  kind: AlertKind;
  title: string;
  body: string;
}

/** A prominent on-screen alert; announced immediately by screen readers. */
export function AlertBanner({ kind, title, body }: Props) {
  return (
    <div className="de-alert" data-kind={kind} role="alert">
      <IonIcon icon={ICONS[kind]} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{body}</p>
      </div>
    </div>
  );
}
