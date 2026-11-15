/**
 * Getting the viewer's attention: system notification (if allowed), a short
 * chime and a vibration. All best-effort — the on-screen banner is the
 * reliable channel.
 */

export type NotificationPermissionState = NotificationPermission | "unsupported";

export function notificationPermission(): NotificationPermissionState {
  return "Notification" in window ? Notification.permission : "unsupported";
}

/** Ask for permission (must be called from a tap) and prepare the worker. */
export async function enableNotifications(): Promise<NotificationPermissionState> {
  if (!("Notification" in window)) return "unsupported";
  const permission = await Notification.requestPermission();
  if (permission === "granted" && "serviceWorker" in navigator) {
    // Android only allows notifications through a service worker.
    await navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  }
  return permission;
}

export async function notify(title: string, body: string, urgent: boolean): Promise<void> {
  chime(urgent);
  navigator.vibrate?.(urgent ? [300, 150, 300, 150, 300] : [200, 100, 200]);
  if (notificationPermission() !== "granted") return;
  const options: NotificationOptions = {
    body,
    icon: "/favicon.svg",
    tag: "donde-estoy", // a newer alert replaces the previous one
    requireInteraction: urgent,
    data: { url: window.location.href },
  };
  try {
    const registration = await navigator.serviceWorker?.getRegistration();
    if (registration) await registration.showNotification(title, options);
    else new Notification(title, options);
  } catch {
    /* notifications blocked at OS level: the banner still shows */
  }
}

/** Two-note chime (three urgent ones for the safety alert) via Web Audio. */
function chime(urgent: boolean): void {
  try {
    const AudioContextClass =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const context = new AudioContextClass();
    const notes = urgent ? [880, 660, 880, 660, 880] : [660, 880];
    notes.forEach((frequency, index) => {
      const start = context.currentTime + index * 0.22;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.25, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.2);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(start);
      oscillator.stop(start + 0.21);
    });
    window.setTimeout(() => void context.close(), notes.length * 220 + 300);
  } catch {
    /* audio not allowed before a user gesture */
  }
}
