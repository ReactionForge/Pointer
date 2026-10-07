# Restore the approved rounded click baseline

The user reported that Art-V3 replaced the rounded motion they liked with the behavior they had rejected. The user also rejected the small triangle drawn by speed trail. Stop adding styles/effects: retain the six-family/eight-palette layout, restore the existing baseline and remove overlays.

## Established reference and exact causes

The pre-V3 P2-final archive is `.local/art-v2-p2-final-candidate/dist/Pointer-v1.3.0-beta.1-windows-x64.zip`, SHA-256 `81f91ced5c79e4ccf69398f92e2c29f62b415d5252b2a03e7cda6d6ae08b60e9`. Its tilt/click assets match current files and immutable Git commit `3511e3ea486d9e897ff752b2d0ee2e19e369e884` byte-for-byte. Commercial and Art-V3 packages also preserve those same native assets. The arrow/frame generators and ClickMotion source remain the original reference (line endings normalized for source comparison).

Art-V3 added an unconditional catalog-hotspot pivot assignment after the rounded arrow had selected its `(20,16)` optical pivot, and excluded tilt/shrink from default built-in resource selection. These two changes displaced the existing reference. The original arrow native assets rotate vector contour before rasterization, while the original general preview renderer samples a padded bitmap. Both original paths are restored and independently tested; the fix does not replace either with a new sampling implementation. ClickMotion timing, easing, strength, press/release behavior and native files are not tuned or regenerated.

Separately, the trail branch drew an additional three-vertex polygon on the cursor canvas based on press frame/strength, not actual pointer speed. It was already present in the older package; it is an independently defective overlay, not evidence of repeated whole-cursor drawing. That polygon branch and the pulse-ring overlay branch are removed. Stored `trail`/`pulse` values are still accepted and round-trip unchanged, render as static cursor pixels, and show a visible inactive explanation in the Motion page. They are absent from recommended motion choices. No replacement small-angle tip or new speed effect was introduced.

## Regression protection

`tests/fixtures/original-rounded-motion.json` was derived from the immutable commit, not Art-V3/current output: 36 original CUR file hashes, 240 native size-variant records, 640 original preview pixel/hotspot hashes, and original time sequences for all six stored modes. Automatic regeneration is not a test step. Golden changes require a separate explicit baseline decision.

Tests check original rounded pixels for tilt/shrink/spring/off across 24/32/48/64 and 96/192 DPI; native assets/default selection remain unchanged. The retired overlays intentionally differ from old output because their extra shapes are disabled. Other recommended families use the original rounded pivot/mode transform semantics and are tested by decoding actual generated CURs at two DPIs, comparing each to its preview raster and fixed hotspot, and flood-filling alpha masks to ensure one solid silhouette. Matching time arrays alone is insufficient.

UI tests preserve retired settings without silently applying changes and verify normal/reduced-motion cancellation for all six families. Reduced-motion suppression resets its internal press clock so toggling motion back on cannot revive a canceled press.

`.local/motion-restore/` contains the frozen before-comparison, original golden provenance, full regression log, 144 actual Qt mouse-event down/hold/release sequences covering all six stored modes, and restoration evidence. Each sequence records eleven frames and a GIF. The source preview is Mock-backed with blocked updater/system operations; the capture does not establish physical-device acceptance. `.local/motion-restored-candidate/` contains a separately frozen repair candidate; all earlier archives and evidence are retained.

The safe preview loads latest source; close and reopen old preview windows. The ordinary candidate EXE uses the real product backend/updater. This work does not install, change Windows cursors/startup, commit/push, or claim user satisfaction. Actual input/DPI, installation/upgrade and user visual confirmation remain outstanding.

Final verification: full unittest discovery passed 182 tests in 59.162 seconds, with one opt-in installation test skipped. Packaged `--diagnose` exited 0 (frozen, Qt 6.11.2; 34 cursor, 4 animated, 32 click resources; 256 package files). All 256 package-file hashes and 36 packaged original reference assets were independently checked against their manifests/oracles. Repair ZIP SHA-256: `90eb8a476ea2387a153e904c250a7fd3111a254ea358d1fb849c28e528869781`. All five previous candidate archive hashes and their retained evidence manifests remain valid. `.local/motion-restore/delivery.json` records the full preservation and repair evidence.
