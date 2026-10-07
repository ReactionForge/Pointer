# Reference settings candidate — review only

The new MyDock/MyFinder reference request supersedes the earlier large workspace direction for the next visual review. The first candidate covers only Appearance and Settings. `ReferenceWindow` is an opt-in Qt review shell; the production entry still uses `MainWindow`. Motion and Test retain their existing pages. No layout approval or rollout to all pages is implied.

The parent inspected the three supplied reference images. Local official Library materialization failed twice because its Windows metadata helper calls unavailable `os.setxattr`; that route was stopped. This implementation uses the parent's measurements and actual local Qt captures, without claiming local reference-pixel inspection.

## Candidate behavior

- Native Windows window frame, dragging, resizing, minimize/maximize/close; 190 px navigation with four entries, blue selected row, compact grouped settings and hairline dividers.
- Opaque light/dark surfaces; no claim of native blur or proprietary Apple materials. Real cursor preview remains above a scrolling property area and a fixed Apply/discard bar. Size 64 gets additional preview height.
- Six existing families, eight palettes with actual cursor thumbnails, historical choices, role/background controls and draft-backed preferences are retained. Startup/pause remain visibly separate immediate actions.
- Review shell reuses existing callbacks and settings models. The review entry uses a Mock backend and blocks OS operations and updater checks/downloads/installation. It does not read or write the user's saved configuration.
- Authoritative animation and original resources remain the motion-restored-final candidate (`d5f3cede52e4fefe2855b617ad1b13d4612c5ab52f6120149af60b436f92f94b`). No renderer, frame, clock, migration or Apply logic changes belong to this task.

## Confirmation visibility fix

All three owned confirmation paths (discard and close, reset corrupt configuration, restore original cursors) use `confirmation_box`. It sets the box's palette and stylesheet explicitly from Pointer's current theme, including text, background, button hover/pressed/focus/disabled states. Yes/No receive Chinese action labels. Keep/cancel is the default and Escape action; window close also preserves the draft. QFileDialog styling is untouched.

The four combinations of simulated system light/dark palettes and Pointer light/dark themes were exercised without changing Windows settings or closing third-party software. This proves Pointer-owned dialog rendering under those palettes; it does not establish Windhawk/MyDock causality or constitute physical Windows theme switching.

## Evidence and review entry

Private review output lives in ignored `.local/reference-ui/`: `pages/` contains 32 Qt captures at 880×620 and 1180×800, light/dark, normal/scrolled/dirty/focused/size-64; `dialogs/` contains 60 confirmation states and the palette matrix. `tray/` contains three newly captured font-initialized menus; these are offscreen menu captures, not a physical tray test. Original evidence directories are preserved.

Run `.local/SAFE-Pointer-Reference-Preview.cmd` to inspect the two-page candidate with isolated operations. This is a source preview using the existing environment, not an installed application or the packaged production UI. `.local/reference-dialog-candidate/` is a separate production ZIP with the confirmation fix and existing approved animation baseline; its default UI remains the previous shell. Do not describe that ZIP as shipping the reference layout.

Pending user decisions: confirm this two-page density/direction and the restored animation baseline before broadening the visual rollout. Real desktop tray, third-party interactions and actual system-theme combinations remain untested.

Validation: full `python -m unittest discover -s tests` ran 190 tests, OK with one skip. Packaged `--diagnose --quiet` passed with Qt 6.11.2, 34 cursor resources, 4 animated resources, 32 click resources and 256 package files. The production confirmation-fix ZIP SHA256 is `462f9f23a3374b65967ba2e9ee70f8141c9261ef9bae2dcb7b8fbb34856ada82`. All seven previous candidate ZIPs, prior evidence manifests and the immutable motion golden remain unchanged. New evidence hashes and delivery metadata are in `.local/reference-ui/sha256.json` and `delivery.json`.

Execution correction: the first packaged diagnosis omitted `--quiet`. Earlier reporting inferred a default report write from the CLI code; the actual original report file has not been confirmed. The newly launched candidate process was stopped, and a corrected invocation used project-local data/report paths and passed. No install, Apply or startup operation was executed; no existing user window was targeted. The exact commands and the remaining uncertainty are recorded in `.local/reference-ui-revision/diagnose-audit.json`.

## Rejected first layout and structural revision

The user rejected the first two-page layout: its general form row pushed six shape choices to the far right, leaving a large empty middle. That layout is not visually approved. The revision uses independent full-width Shape and Palette galleries above the ordinary property rows. Six shapes share the available width (six columns at reviewed widths, three when narrower); eight real paired palette previews remain in four columns. At the default 32 px size, all six shapes and all eight palette choices are visible on the 880×620 initial screen. At 64 px, the larger preview means the second palette row needs ordinary vertical scrolling; accessible target sizes are preserved. Editing content caps at 960 DIP; the preview caps at 740 DIP and has a visible subtle surface boundary. Apply remains fixed.

New source-only captures are in `.local/reference-ui-revision/pages/`, at 880×620, 1180×800 and 1800×900 in both themes. This revision uses opaque color levels and thin borders, not actual frosted blur. It remains pending visual confirmation. No additional production package was built for this revision; the preceding confirmation-fix ZIP is unchanged.
