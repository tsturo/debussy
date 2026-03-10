VISUAL VERIFICATION (for beads with the `frontend` label):
- Start the dev server using the command from the bead description
- Use Playwright MCP (browser_navigate, browser_take_screenshot) to verify the UI works end-to-end
- Run any existing Playwright tests: npx playwright test
- browser_close and kill the dev server when done
- Include visual findings in your acceptance comment
