import type { Meta, StoryObj } from "@storybook/react";

import { ApprovalPendingBadge } from "./ApprovalPendingBadge";
import { apiClient } from "../api/client";
import "../i18n";

const meta: Meta<typeof ApprovalPendingBadge> = {
  title: "Components/ApprovalPendingBadge",
  component: ApprovalPendingBadge,
};

export default meta;

type Story = StoryObj<typeof ApprovalPendingBadge>;

function withMockedTotal(total: number) {
  return (Story: React.ComponentType) => {
    apiClient.defaults.adapter = (config) =>
      Promise.resolve({
        data: {
          success: true,
          data: { items: [], total, limit: 1, offset: 0 },
          error: null,
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
        request: {},
      });
    return <Story />;
  };
}

export const NoPending: Story = {
  decorators: [withMockedTotal(0)],
  args: { children: <span style={{ padding: "0 8px" }}>Approvals</span> },
};

export const ThreePending: Story = {
  decorators: [withMockedTotal(3)],
  args: { children: <span style={{ padding: "0 8px" }}>Approvals</span> },
};
