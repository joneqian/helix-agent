import { ConfigProvider, App as AntApp } from "antd";
import { Route, Routes } from "react-router-dom";

import { useTheme } from "./theme/ThemeContext";
import { darkTheme, lightTheme } from "./theme/antdTheme";
import { Shell } from "./components/Shell";
import { CommandPaletteProvider } from "./components/CommandPalette";
import { AppRouter } from "./router";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { SetupGate } from "./auth/SetupGate";
import { AuthCallback } from "./pages/AuthCallback";
import { AuthSilent } from "./pages/AuthSilent";
import { Login } from "./pages/Login";
import { SetupWizard } from "./pages/SetupWizard";

export default function App() {
  const { mode } = useTheme();
  const themeConfig = mode === "dark" ? darkTheme : lightTheme;

  return (
    <ConfigProvider theme={themeConfig} componentSize="middle">
      <AntApp>
        {/* SetupGate probes /v1/setup/status and steers an
            un-initialized platform to /setup *before* ProtectedRoute can
            kick off an OIDC redirect (no account exists yet to log in
            with). */}
        <SetupGate>
          <Routes>
            <Route path="/setup" element={<SetupWizard />} />
            <Route path="/login" element={<Login />} />
            {/* OIDC callback + silent renew routes must stay outside
                ProtectedRoute — the user is unauthenticated at the moment
                the IdP redirects them here. */}
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="/auth/silent" element={<AuthSilent />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <CommandPaletteProvider>
                    <Shell>
                      <AppRouter />
                    </Shell>
                  </CommandPaletteProvider>
                </ProtectedRoute>
              }
            />
          </Routes>
        </SetupGate>
      </AntApp>
    </ConfigProvider>
  );
}
