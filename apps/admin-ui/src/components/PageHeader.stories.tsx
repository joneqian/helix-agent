import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { Button } from "antd";
import { Activity } from "lucide-react";

import { PageHeader } from "./PageHeader";

const meta: Meta<typeof PageHeader> = {
  title: "Stream H/PageHeader",
  component: PageHeader,
  parameters: { layout: "padded" },
  decorators: [
    (Story) => (
      <MemoryRouter>
        <Story />
      </MemoryRouter>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof PageHeader>;

export const Default: Story = {
  args: {
    title: "Runs",
    icon: <Activity size={18} strokeWidth={1.75} />,
    subtitle: "All agent runs across the current tenant scope.",
  },
};

export const WithActions: Story = {
  args: {
    title: "Runs",
    icon: <Activity size={18} strokeWidth={1.75} />,
    subtitle: "All agent runs across the current tenant scope.",
    actions: <Button type="primary">New run</Button>,
  },
};

export const WithBackTo: Story = {
  args: {
    title: "run_01HXYZ",
    backTo: { label: "Runs", to: "/runs" },
    subtitle: "Started 2 minutes ago · paused for approval",
  },
};
