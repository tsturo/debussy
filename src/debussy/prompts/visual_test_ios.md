VISUAL VERIFICATION (for tasks with the `frontend` tag):
- Build the project for simulator:
  xcodebuild -workspace <name>.xcworkspace -scheme <scheme> -destination 'platform=iOS Simulator,name=iPhone 16' build 2>&1 | tail -5
- If build fails, report the build error in your acceptance comment
- Run UI tests if they exist:
  xcodebuild test -workspace <name>.xcworkspace -scheme <scheme> -destination 'platform=iOS Simulator,name=iPhone 16'
- Install and launch on simulator, navigate to relevant screens
- Take screenshots: xcrun simctl io booted screenshot /tmp/acceptance_screenshot.png
- Read the screenshot to verify it matches the task descriptions
- Include visual findings in your acceptance comment
