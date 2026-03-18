VISUAL VERIFICATION (for tasks with the `frontend` tag):
- Start the dev server using the command from the task description
- Use Playwright MCP (browser_navigate, browser_take_screenshot) to verify the UI works end-to-end
- Run any existing Playwright tests: npx playwright test
- browser_close and kill the dev server when done
- Include visual findings in your acceptance comment
