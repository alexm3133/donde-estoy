import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/manrope";
import "@ionic/react/css/core.css";
import "@ionic/react/css/normalize.css";
import "@ionic/react/css/structure.css";
import { setupIonicReact } from "@ionic/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./i18n";
import "./theme/tokens.css";
import "./theme/base.css";

// One look on every platform: the design is ours, not iOS' or Material's.
setupIonicReact({ mode: "md" });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
