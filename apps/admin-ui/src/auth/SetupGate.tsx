/**
 * First-run setup gate.
 *
 * Probes ``GET /v1/setup/status`` once on mount and steers the whole app
 * before :ref:`ProtectedRoute` (and therefore before any OIDC redirect)
 * gets a chance to run:
 *
 *   - platform **not** initialized + not already on ``/setup`` →
 *     redirect to ``/setup`` (logging in is pointless — no account
 *     exists yet);
 *   - platform initialized + sitting on ``/setup`` → redirect home so a
 *     stale bookmark doesn't strand the user on a dead wizard.
 *
 * Failure of the probe (backend unreachable) is non-fatal: we warn and
 * fall through to the normal flow rather than trapping the user in a
 * loading state or a redirect loop.
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { getSetupStatus } from "../api/setup";

type GateState =
  | { phase: "loading" }
  | { phase: "ready"; initialized: boolean };

const SETUP_PATH = "/setup";

export function SetupGate({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [state, setState] = useState<GateState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    getSetupStatus()
      .then((status) => {
        if (cancelled) return;
        setState({ phase: "ready", initialized: status.initialized });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // Backend unreachable — don't block the app. The normal flow
        // (login / protected routes) takes over and surfaces its own
        // errors on the next API call.
        console.warn("[SetupGate] setup status probe failed; passing through", err);
        setState({ phase: "ready", initialized: true });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.phase === "loading") {
    return (
      <div
        aria-hidden
        data-testid="setup-gate-loading"
        style={{ minHeight: 120, padding: 24, opacity: 0.4 }}
      />
    );
  }

  const onSetup = location.pathname === SETUP_PATH;

  if (!state.initialized && !onSetup) {
    return <Navigate to={SETUP_PATH} replace />;
  }
  if (state.initialized && onSetup) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
