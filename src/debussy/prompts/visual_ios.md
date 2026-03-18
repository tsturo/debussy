FRONTEND VISUAL VERIFICATION (only if this task has the `frontend` tag):

Before committing, perform visual verification:

A) BUILD AND RUN ON SIMULATOR:
   - Determine the Xcode project/workspace: look for *.xcworkspace (prefer) or *.xcodeproj
   - Build for simulator:
     xcodebuild -workspace <name>.xcworkspace -scheme <scheme> -destination 'platform=iOS Simulator,name=iPhone 16' build 2>&1 | tail -5
   - If build fails, fix errors and retry
   - Boot simulator if needed: xcrun simctl boot "iPhone 16"
   - Install and launch:
     xcrun simctl install booted <path-to-built-app>
     xcrun simctl launch booted <bundle-id>

B) VISUAL VERIFICATION LOOP:
   - Take a screenshot: xcrun simctl io booted screenshot /tmp/screenshot.png
   - Read the screenshot file to evaluate it against the task description
   - If UI navigation is needed, use xcrun simctl or deep links to reach the right screen
   - If it looks wrong or incomplete, fix the code, rebuild, and repeat
   - Max 3 iterations — if still broken after 3, commit what you have and note issues in a comment

C) WRITE UI TESTS (if appropriate):
   - Add XCUITest or snapshot tests that verify the visual behavior
   - Run: xcodebuild test -workspace <name>.xcworkspace -scheme <scheme> -destination 'platform=iOS Simulator,name=iPhone 16' -only-testing:<TestTarget>
   - Fix until tests pass

D) XCODE PREVIEWS (for SwiftUI views):
   - Ensure PreviewProvider / #Preview is defined for modified views
   - Build to verify previews compile: xcodebuild build -workspace <name>.xcworkspace -scheme <scheme> -destination 'platform=iOS Simulator,name=iPhone 16'
