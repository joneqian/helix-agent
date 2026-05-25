/**
 * Storybook preview — Stream H.1b PR 4.
 *
 * Every story renders inside the same provider stack the production
 * SPA mounts so tokens / theme / i18n / routing work uniformly. The
 * axe addon background runs against every story, so a11y regressions
 * show up in the toolbar without explicit assertions.
 */
import "../src/theme/tokens.css";
import "../src/theme/global.css";
import "../src/i18n";

import { ConfigProvider, App as AntApp } from "antd";
import { MemoryRouter } from "react-router-dom";
import type { Preview } from "@storybook/react";

import { ThemeProvider, useTheme } from "../src/theme/ThemeContext";
import { darkTheme, lightTheme } from "../src/theme/antdTheme";

function ThemedAntApp({ children }: { children: React.ReactNode }) {
  const { mode } = useTheme();
  return (
    <ConfigProvider theme={mode === "dark" ? darkTheme : lightTheme} componentSize="middle">
      <AntApp>{children}</AntApp>
    </ConfigProvider>
  );
}

const preview: Preview = {
  parameters: {
    layout: "centered",
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    a11y: {
      // Match the E2E threshold — only block on serious + critical.
      element: "#storybook-root",
      config: { rules: [{ id: "color-contrast", enabled: true }] },
    },
  },
  decorators: [
    (Story) => (
      <ThemeProvider>
        <ThemedAntApp>
          <MemoryRouter>
            <Story />
          </MemoryRouter>
        </ThemedAntApp>
      </ThemeProvider>
    ),
  ],
};

export default preview;
