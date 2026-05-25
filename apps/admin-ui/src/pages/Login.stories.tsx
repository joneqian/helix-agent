import type { Meta, StoryObj } from "@storybook/react";

import { Login } from "./Login";
import { AuthProvider } from "../auth/AuthContext";

const meta: Meta<typeof Login> = {
  title: "Stream H/Login",
  component: Login,
  parameters: { layout: "fullscreen" },
  decorators: [
    (Story) => (
      <AuthProvider>
        <Story />
      </AuthProvider>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof Login>;

/** OIDC-unconfigured deploy — token-paste is the only path. */
export const TokenPasteOnly: Story = {
  // Default behaviour when VITE_OIDC_ISSUER + VITE_OIDC_CLIENT_ID are
  // not set at build time (Storybook env). The component reads env at
  // render time, so no extra wiring is required here.
};
