VISUAL REVIEW (for beads with the `frontend` label):
- Build the project for simulator:
  xcodebuild -workspace <name>.xcworkspace -scheme <scheme> -destination 'platform=iOS Simulator,name=iPhone 16' build 2>&1 | tail -5
- If build fails, reject with the build error
- Install and launch on simulator, navigate to the relevant screen
- Take screenshots: xcrun simctl io booted screenshot /tmp/review_screenshot.png
- Read the screenshot to verify it matches the bead description
- Check that SwiftUI previews compile for modified views
- Include visual findings in your review comment
