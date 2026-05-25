/**
 * Storybook main config — Stream H.1b PR 4.
 *
 * Vite-driven, mirrors apps/admin-ui's Vite config so stories load the
 * same tokens.css + global.css the production SPA does. Stories live
 * next to their components as ``*.stories.tsx``.
 */
import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-essentials", "@storybook/addon-a11y"],
  framework: { name: "@storybook/react-vite", options: {} },
  docs: { autodocs: "tag" },
  typescript: { check: false },
};

export default config;
