import { IonApp } from "@ionic/react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { HomePage } from "./pages/HomePage";
import { RunPage } from "./pages/RunPage";
import { ViewerPage } from "./pages/ViewerPage";

/**
 * Three screens:
 *   /          runner: set up an outing
 *   /run       runner: sharing live
 *   /s/:token  viewer: the page behind a share link
 */
export function App() {
  return (
    <IonApp>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/run" element={<RunPage />} />
          <Route path="/s/:token" element={<ViewerPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </IonApp>
  );
}
