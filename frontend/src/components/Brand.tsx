import "./Brand.css";

/** Logo mark + wordmark. */
export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`de-brand${compact ? " de-brand--compact" : ""}`}>
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <rect width="64" height="64" rx="16" fill="var(--de-night-950)" />
        <path d="M6 50 24 22l9 13 7-9 18 24z" fill="var(--de-night-600)" />
        <circle cx="40" cy="25" r="7.5" fill="var(--de-sunset-500)" />
        <circle cx="40" cy="25" r="2.8" fill="var(--de-night-950)" />
      </svg>
      <span className="de-brand__name">¿Dónde estoy?</span>
    </span>
  );
}
