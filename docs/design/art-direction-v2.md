# Pointer art and interaction revision, 2026-10-06

The user rejected the previous navigation placement/size, non-rounded styles, non-monochrome palettes and weak press feedback, and authorized continued substantial implementation. This revision is a reviewable candidate, not a new record of user visual approval. Earlier B composition approval and previous screenshots do not approve these changes.

## Result

- Four consistent icon-and-text navigation targets move to an adaptive left rail: 95 × 48 logical px at 880 × 620, 135 × 48 at wider captures. The Apply/discard footer remains visible and stable.
- The appearance inspector shows four family choices and all three curated palettes in the initial 880 px viewport. Preview background, observation scale and system adaptation have distinct direct controls.
- New `quill`, `facet` and `outline` families cover all 17 roles, including loading, resizing, pen, location and person roles. They share their respective stroke, contour and terminal treatment rather than replacing only the arrow and hand. Rounded remains unchanged. Legacy precision/falcon/pixel geometry and imported colors remain available without silent conversion.
- Curated palettes are black/white, slate and stone. Slate body colors are #526575 / #bcc8d2; stone #6a625a / #d8cfc3. Light outlines are white, dark outlines #202124. Historical palette definitions are retained; choosing a palette changes only four body/outline colors and preserves glow and other settings.
- Shape/palette selection, navigation, Apply and the preview surface have distinct hover, press and keyboard-focus feedback. Actual-size previews provide a local button scene. Light press/tilt/off recipes edit the draft; reduced UI motion retains immediate press feedback without animated preview frames.
- Draft/apply/pause/startup semantics, backup preservation and update behavior remain those of the product. Mock review entry points separately block updater services and system operations.

## Art provenance and inspection

Primary references: [Capitaine](https://github.com/keeferrourke/capitaine-cursors) and [Bibata](https://github.com/ful1e5/Bibata_Cursor) informed family consistency and silhouette comparison. No third-party SVG, bitmap or cursor theme was copied into product assets; these families use original local Pillow geometry. Cursor semantics follow [Windows cursor documentation](https://learn.microsoft.com/en-us/windows/win32/menurc/about-cursors) and [Qt QCursor](https://doc.qt.io/qt-6/qcursor.html).

The current Library attachment was accessible as metadata/extracted text, not image pixels through the supported Windows flow. It is not claimed as a locally inspected image. Review relies on the parent's image observations and actual locally rendered Qt/Pillow output.

`scripts/render_art_review.py --assets` produces 102 native CUR/ANI assets in `assets/cursors/art-v2/`, with 24/32/48/64 variants. `scripts/capture_art_candidate.py` captures only its own Mock window. Native role sheets, hotspot/bounds records and light/dark interaction captures are in ignored `.local/art-direction-v2/`. Enlarged preview illustrations are labeled separately from actual-size specimens.

The candidate will be packaged separately in `.local/art-v2-candidate/`; previous commercial/family archives and frozen evidence remain preserved. `.local/SAFE-Pointer-Art-V2-Preview.cmd` opens current source with a Mock backend and blocked updates. The ordinary candidate EXE uses the real product backend and updater.

Validation results are recorded in `.local/art-direction-v2/final-unit.log`, `build.log`, `diagnose.json` and `delivery.json`. Simulated wide-window and offscreen captures do not establish physical-device input/DPI behavior. Physical mouse/keyboard/trackpad, installation/upgrade and user visual acceptance remain to be exercised before a release claim. No commit, push, release, install or Windows cursor/startup mutation is part of this candidate delivery.

Final checks: full unittest discovery passed 171 tests in 54.426 seconds with one opt-in installation integration test skipped. The frozen candidate's `--diagnose` exited 0 (Qt 6.11.2; 34 cursor, 4 animated, 32 click resources; 256 packaged files). Native asset headers confirm 90 CUR and 12 ANI files; each CUR contains four size variants. The actual `--show` entry branch was exercised offscreen with blocked manual update and zero Apply/workers, not launched on the physical desktop.

Candidate ZIP SHA-256: `f124acd922f9ba1f65360e80720e63022fc290c460172fd0575e53a0cf2f3122`. The commercial and family ZIP hashes remain unchanged, and all 36 frozen commercial screenshots match their prior manifest. The current assets/captures have a separate `.local/art-direction-v2/sha256.json` manifest. Source remains uncommitted on DEV at `3511e3ea486d9e897ff752b2d0ee2e19e369e884`.

## Independent review follow-up

Three P2 findings were addressed without treating independent review as user visual acceptance:

1. Outline hand, pen and move receive local adjustments only below 32 px: connected finger ink, a solid pointed small pen and separated shorter four-direction arrowheads. `.local/art-direction-v2-p2/small-size-comparison.json` confirms exactly six changed 24 px/theme samples, all 130 other outline samples pixel-identical, and every hotspot unchanged. New native sheets are in that directory's `render-review/`; earlier sheets are preserved. Native assets now represent the follow-up and have a new manifest.
2. A persistent, muted `历史造型` disclosure exposes the three legacy styles without competing with the four primary cards. It remains reachable after a new family is applied; collapse survives ordinary synchronization. An actual Mock Apply round-trip test and `final/legacy-roundtrip.json` confirm return to the original settings as a draft, retaining the newly applied family until another explicit Apply. Expanded light/dark screenshots accompany the record.
3. The observation controls have the short `预览` heading and `浅 / 深 / 对比` labels. System adaptation remains separately labeled in the inspector. Narrow-window captures and control-fit regressions cover the added label.

The follow-up candidate is independently packaged in `.local/art-v2-p2-final-candidate/`; the original `f124acd...` archive is preserved. Current-source `.local/SAFE-Pointer-Art-V2-Preview.cmd` continues to use the guarded Mock entry point; close and reopen an existing preview to load this revision. Tests, diagnosis and final hashes are recorded separately under `.local/art-direction-v2-p2/`. Earlier art-v2 manifest entries for mutable native assets describe the earlier revision; its frozen image entries remain valid.

Final follow-up verification: unittest discovery passed 172 tests in 56.643 seconds (one opt-in installation test skipped). Packaged diagnosis exited 0 with frozen true, Qt 6.11.2, 34 cursor/4 animated/32 click resources and 256 packaged files. Final ZIP SHA-256 is `81f91ced5c79e4ccf69398f92e2c29f62b415d5252b2a03e7cda6d6ae08b60e9`. Mock Apply evidence explicitly labels its result as simulation; no physical desktop preview or system Apply was performed.
