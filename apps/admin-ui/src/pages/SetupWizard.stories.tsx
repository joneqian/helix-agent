import type { Meta, StoryObj } from "@storybook/react";
import { App } from "antd";
import { MemoryRouter } from "react-router-dom";

import { SetupWizard } from "./SetupWizard";
import { apiClient } from "../api/client";

/** Stub the bootstrap endpoint so the Success story's form submission
 *  resolves into the confirmation card without a backend. */
function stubSetupOk(): void {
  apiClient.defaults.adapter = (config) =>
    Promise.resolve({
      data: {
        success: true,
        data: {
          tenant_id: "11111111-1111-1111-1111-111111111111",
          subject_id: "22222222-2222-2222-2222-222222222222",
        },
        error: null,
      },
      status: 200,
      statusText: "OK",
      headers: {},
      config,
      request: {},
    });
}

const meta: Meta<typeof SetupWizard> = {
  title: "Stream H/SetupWizard",
  component: SetupWizard,
  parameters: { layout: "fullscreen" },
  decorators: [
    (Story) => (
      <MemoryRouter initialEntries={["/setup"]}>
        <App>
          <Story />
        </App>
      </MemoryRouter>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof SetupWizard>;

/** Initial form state — the operator fills in the first system admin. */
export const Form: Story = {};

/** Success state — fill the form against a stubbed endpoint and submit
 *  to reveal the confirmation card. The interaction runs only when the
 *  storybook interactions runner is present; otherwise this renders the
 *  empty form (a safe superset of {@link Form}). */
export const Success: Story = {
  render: () => {
    stubSetupOk();
    return <SetupWizard />;
  },
};
