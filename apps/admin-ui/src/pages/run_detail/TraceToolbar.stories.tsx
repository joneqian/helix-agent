import type { Meta, StoryObj } from "@storybook/react";

import { TraceToolbar } from "./TraceToolbar";
import "../../i18n";

const meta: Meta<typeof TraceToolbar> = {
  title: "RunDetail/TraceToolbar",
  component: TraceToolbar,
};

export default meta;

type Story = StoryObj<typeof TraceToolbar>;

export const WithTrace: Story = {
  args: { traceId: "9f8b2a3c4d5e6f70" },
};

export const NoTrace: Story = {
  args: { traceId: null },
};
