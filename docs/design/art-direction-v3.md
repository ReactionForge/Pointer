# Pointer: more choice, coherent press motion

The latest user request supersedes the outline refinement: more palettes, more distinct practical single-body styles, and press motion consistent with rounded. This candidate implements those requests; it does not record user visual approval.

## Root cause and resulting behavior

The retired outline arrow's static renderer adds a separate solid triangle on top of a hollow outline. This explains the rejected double contour even at frame zero; the Qt preview draws one cursor bitmap, not a static cursor plus a press copy. The existing outline ID and renderer remain available in the muted historical disclosure so saved settings are not silently rewritten. Outline is removed from the recommended cards.

Recommended families are rounded, quill, facet, lance, droplet and rectilinear. Three new single contours provide a long spearhead, a curved drop body and an upright right-angle pointer. They differ in silhouette and also carry their own stroke weight, corner treatment, terminals and role proportions across all 17 roles. No overlay tip patch or duplicate arrow is used for the three new families. Original rounded and previous frozen candidates are preserved.

Eight curated palettes are black/white, slate, stone, sage, clay, mauve, ocean and rose. The five additions use subdued cool/warm bodies with white light-channel and near-black dark-channel outlines. Historical bright preset data remain compatibility data, not the recommended gallery. Palette changes still affect only four colors, preserving style, glow, size and motion. The inspector scrolls to the additional choices while preview and Apply remain fixed.

Press mismatch had two concrete sources: style-specific pivot selection, and rounded defaults selecting historical built-in press assets instead of the shared live renderer. All families now use their role's catalog hotspot as their affine anchor. Default animated configurations also generate their native frames through that renderer. Mode, strength, press/release durations, easing and the ClickMotion frame sequence are independent of style. Existing stored durations/modes are not rewritten. Off remains static; reduced UI motion preserves immediate feedback without moving the specimen.

## Evidence and delivery

Native 24/32/48/64 pixel, light/dark sheets are in `.local/art-v3/render-review/`; generated assets are isolated in `assets/cursors/art-v3/`. All eight palettes appear in `curated-palettes-native-32.png`. Current light/dark windows and interaction states are in `.local/art-v3/final/`; preview observation keeps its `预览 / 浅 / 深 / 对比` labels and history remains reachable.

`scripts/capture_motion_review.py` uses actual Qt mouse-down/up events in a guarded Mock window, sampling a deterministic clock through the same ClickMotion used by preview and Windows. It records 48 combinations of six styles × two roles × tilt/shrink × two backgrounds, each with rest/down/20ms/40ms/pressed/hold/release/40ms/80ms/120ms/restored PNGs and an animated GIF. Window-deactivation cancellation is checked for each sequence. These are enlarged preview specimens, not a physical-device acceptance test. `motion-review/timeline.json` exposes the sampled frames and timing.

Regression tests compare actual affine transforms/hotspots for every recommended family, both click roles, all five active modes and all four press frames; default native resources must use shared generation. UI regression protects historical outline settings and the existing Mock Apply round-trip. `.local/art-v3/` holds the final full-test log, build log, diagnosis and manifest. The candidate is separately frozen under `.local/art-v3-candidate/`; previous ZIPs are preserved.

The user's current Library attachment was read through the supported route, which returned extracted text and a warning that image pixels were unavailable on this Windows environment. It is not claimed as a locally viewed image. The parent supplied the actual image observation, and local rendered output independently confirmed the static overlay root cause. No fallback transfer bypass was used.

`.local/SAFE-Pointer-Art-V3-Preview.cmd` loads current source with blocked updater services and Mock system actions. Existing previews need closing and reopening to load new source. The ordinary candidate EXE retains the real backend/updater. No system Apply, installation, startup mutation, Git write or upload forms part of this review delivery. User visual acceptance, physical input/DPI and installation/upgrade remain unverified.

Full unittest discovery passed 175 tests in 74.101 seconds, with one opt-in installation integration test skipped. The final native matrix has 150 CUR and 20 ANI files, with four static size variants per CUR. Independent candidate ZIP SHA-256: `be3fd5ae6fe996b5759313d75cafe52a79daaa0d8d47429fcc369d69fadedc4a`. Diagnostic and preservation results are recorded in `.local/art-v3/delivery.json` after checking the packaged executable and the prior evidence manifests.
