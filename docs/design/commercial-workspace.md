# Pointer commercial workspace candidate

Date: 2026-10-06. Branch: DEV. Baseline: `3511e3ea486d9e897ff752b2d0ee2e19e369e884`. Local candidate, uncommitted and unpublished.

The user authorized takeover after ending the original session, then requested heavy reconstruction of weak interaction, excessive text, accidental wheel edits and navigation/action placement. The parent supplied that explicit transcript and confirmed there is no competing Pointer writer. This supersedes the historical B topology lock; it does not approve the finished candidate or transfer Pointer's Apple-inspired direction to another project.

| Before | After | Why |
| --- | --- | --- |
| Several preview regions and scattered settings/actions | One fixed preview stage, one property inspector, adjacent discard/Apply footer | Keep observation and the editing/commit path stable |
| Closed value controls consume wheel input | Wheel routes once to the page, preserving event metadata; popup views and keyboard editing remain native | Scrolling must not edit configuration |
| Eight palettes communicate through small color dots | Paired rendered light/dark cursor specimens, short names and a selected check; two columns at 350 logical px | Show the actual color relationship without an additional editor |
| Presets also reset glow implicitly | Presets, matching and reset affect only four body/outline colors; glow and other settings persist | Limit actions to their visible semantics |
| Long motion descriptions compete with controls | Six short mode names and stacked labeled sliders with tooltips | Fit the inspector while preserving all modes and parameters |
| Preview caches share enlarged and actual-size entries | Cache distinguishes scale and render DPI; full canvas at actual size | Avoid the 64px cache collision and clipping |
| A matching draft appears as saved success | Neutral no-pending-changes label, separate paused/running state, operation feedback only after completion | Distinguish configuration state from runtime and results |
| Paused Apply starts the service | GUI Apply preserves the previous runtime state; CLI defaults remain unchanged | Applying edits must not implicitly resume |

## Reference adaptations

[Microsoft NavigationView](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/navigationview) informed predictable navigation and low-frequency Settings placement. Pointer uses its existing native Qt shell, not a WinUI dependency.

[QGIS scroll-area source](https://github.com/qgis/QGIS/blob/master/src/gui/qgsscrollarea.cpp) demonstrates the accidental-edit problem in value widgets inside scroll areas. Pointer implements an independent explicit wheel-routing policy; no QGIS code was copied. [Qt QWheelEvent](https://doc.qt.io/qt-6/qwheelevent.html) defines coordinates, deltas, phase, inversion and device metadata preserved during forwarding.

## Behavior and safety

Role/background/scale observation does not enter CursorSettings. Appearance, motion, shake/game/tray/autoupdate remain draft-backed. Startup and pause/resume retain their explicit immediate transactions. Apply is guarded during loading, invalid input and an unchanged draft; errors retain the draft. Original cursor backup and an unchanged startup entry remain preserved by the existing application transaction and its regressions. The optional preserve_runtime flag passes through the portable helper and retains CLI default behavior.

Preview surfaces have immediate hover, mouse-press and keyboard-focus feedback, including when cursor motion is off. Reduced UI motion uses the Qt style animation hint. No cursor geometry, hotspot or system motion renderer was redesigned.

## Evidence and review

Safe review: `.local/SAFE-Pointer-Commercial-Preview.cmd` runs `scripts/capture_commercial_ui.py --show` with a Mock backend blocking Apply, pause/resume, restore and startup. It creates no tray or update check. An ordinary packaged executable uses the real backend and is a different entry point.

Final Qt window-only captures: `.local/commercial-redesign/final/`; light/dark 1180x800 and 880x620 appearance, inline colors, motion, tests and settings, plus actual-size, loading and simulated-error states. `measurements.json` reports logical control-center distances and simple visible-action proxies, not measured human performance. Synthetic DPR captures are not physical monitor calibration.

Validation logs and the isolated new build belong in `.local/commercial-redesign/` and `.local/commercial-candidate/`. The historical `.local/family-candidate/` package is preserved. No installation, actual system Apply, registry/startup change, public upload, commit, push, merge, tag or release is authorized or performed in this reconstruction.

User visual acceptance, physical keyboard/mouse/trackpad and display-DPI testing, and installation/upgrade testing remain separate. Passing regression tests and packaged diagnosis do not establish commercial release readiness.

Final verification: full unittest discovery ran 161 tests in 55.715s, OK with one opt-in installation integration test skipped. Packaged --diagnose exit 0: frozen true, Qt 6.11.2, 34 cursor resources, 4 animated resources, 32 click resources, 256 packaged files. Logs: `.local/commercial-redesign/final-unit.log`, `build.log`, `diagnose.json`.

ZIP: `.local/commercial-candidate/dist/Pointer-v1.3.0-beta.1-windows-x64.zip`. SHA-256: `19d87b609a966b0e605715c55404e1ed1b4f99a2afd388a5a138d4cc05495f90`. The preserved P2 ZIP hash remains `ad7b9220064c619e7fbfd1d3996bcb4d62247d611982099d603340976879e372`.

Final light/dark captures at both widths have zero inspector horizontal scroll and two preset columns. Apply/discard center distance is 110 logical px; baseline was 645 at 1180 and 465 at 880. Aurora-to-Apply center distance is 344.3/162.2 logical px; baseline 823.9/570.7. The preset-to-Apply proxy is two visible actions instead of a required initial scroll plus two actions. These are UI geometry proxies, not physical user-task timing. Actual-size 64px, narrow palette-bottom, mouse hover/press, role popup and synthetic DPR2 captures were visually inspected.

No Pointer-named process was found during read-only process lookup. This does not identify a source-launched Python instance or prove which build produced the user's attachment. Official Library materialization failed on Windows metadata support; no workaround was used. Parent pixel observations and locally rendered Qt windows were used as the supported evidence instead.

## Safety-preview updater correction

The initial Mock backend did not isolate MainWindow's direct manual updater calls. The review entry points now construct scripts.safe_preview.SafePreviewWindow, which blocks the Settings check button, silent check callback and update-dialog callback with an explicit isolation message. A process-local service context also blocks updater check/download/upgrade functions and update-dialog download/upgrade aliases. Shipped product update behavior is unchanged. The commercial, family and design-review Mock entry points all use this guard.

Targeted regressions exercise the real Settings button and all reachable update callbacks with zero updater, download, dialog-construction, upgrade and urllib network calls. Direct download/upgrade guard regressions verify blocking before network and restoration after the process-local context. An older UI test fixture had enabled automatic update timers; its Mock settings now disable tray and auto-check, avoiding unrelated pending timer calls during safety verification.

Safety evidence: .local/commercial-redesign/safety-unit.log (3 tests), safety-ui-confirm.log (related UI suite), safety-capture.log and safety-review/ (new offscreen run, final images preserved). safety-show-smoke.log exercises the actual --show event-loop branch offscreen, clicks Settings check-update, verifies isolation and closes only its own test window. A physical visible-window CMD launch has not been exercised. The existing .local/SAFE-Pointer-Commercial-Preview.cmd now loads the corrected scripts; an already-open preview must be reopened to load them.

No candidate rebuild is needed for this script/test-only correction. The frozen commercial ZIP contains no capture/safety scripts; it is the ordinary product with real backend/updater. Its SHA-256 remains 19d87b609a966b0e605715c55404e1ed1b4f99a2afd388a5a138d4cc05495f90. All 36 frozen final screenshots match their recorded hashes. No system actions, installation, upload or Git write were performed.
