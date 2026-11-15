import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Capacitor wraps the built web app (`dist/`) in a native Android / iOS shell.
 * Native projects are not committed; create them with:
 *
 *   npm run build && npx cap add android && npx cap sync
 *
 * A native build must know where the API lives: set VITE_API_BASE at build
 * time (see src/api/client.ts).
 */
const config: CapacitorConfig = {
  appId: "app.dondeestoy",
  appName: "¿Dónde estoy?",
  webDir: "dist",
};

export default config;
