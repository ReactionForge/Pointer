# Accepted v2 dual workspace — source review candidate

## Authority

The parent showed the complete dual-workspace concept and the user replied “这次设计挺好”. The authoritative reference is Library `libfile_b7a5e9fa7bf48191be8133b87aa77c55`, **version 2**, file `exec-776ac486-56a9-4316-b0c8-8fc8f74aeb23.png`. Local official read confirmed this identity/version but returned only extracted text with a native-pixels-unavailable warning. Implementation follows the parent's explicit visible-pixel specification; it does not claim a local pixel comparison with that image. Version 0/1 vertical experiments are retained and are not the design target.

## Implemented structure

`DualWindow` is a new opt-in two-page shell. It keeps the accepted graphite/blue sidebar and compact tokens, while replacing the vertical preview/property stack with two work columns: fixed observation on the left and independently scrolling properties on the right, with a thin divider. Available column space is apportioned approximately 46:54. Sidebar is 190 DIP; content margins are 24 DIP and maximum editing width is 1100 DIP. Main review size is 1180×880; it is not automatically maximized. Footer spans both columns and remains fixed at 52 DIP.

The left column contains a preview heading and enlarged/1:1 choices, two uncluttered light/dark stages, five common real role thumbnails, the complete existing 17-role selector, a short press-trial action and actual-size information. Stages use the same cached cursor pixmaps, effective theme, frame selection and DPI choices as the existing preview; the example-button decoration was removed from this new stage so text no longer overlaps the cursor. Its inherited pointer/keyboard/cancel handling is retained. The trial button uses the existing `set_down`/`clear_press`, with focus/hide/deactivation/ungrab/leave cancellation. No renderer, motion transform, clock or original resource was edited.

The right column contains six real families in a common 3×2 panel, eight real paired palette thumbnails in a common 4×2 panel, then grouped size/adaptation/custom rows. Only selected specimens get a blue thin border/subtle fill. Historical shapes remain under More; custom colors/glow expand inside the same right scroll area. At 880 px, palettes use two columns to preserve their real thumbnails and targets; remaining settings scroll normally. Neither the left observations nor Apply move with that scroll. Settings uses the same shell/tokens with a full-width grouped settings panel and the existing immediate-vs-draft semantics.

## Explicit differences from the supplied concept

- Reference cursor silhouettes are illustrative; real rounded/family pixels and restored original motion are used.
- Native Windows title bar/resize/Snap/system-menu behavior remains; widget screenshots exclude that native chrome.
- Complete role/history/reset compatibility controls remain accessible. At 880 px the palette becomes 2×4 rather than shrinking four columns; there is ordinary vertical scrolling, not forced all-controls-first-screen packing.
- Press trial is a lightweight control using existing preview input, not a new effect or timeline.
- Real client material is still **opaque color levels and thin boundaries**, not frosted blur. A hidden instance of this new Mock shell accepted the official DWM Mica attribute, read back 2 and restored 0 on close. High-contrast/older-platform rejection is simulated, final DWM pixels are not proven, and no desktop/wallpaper capture is used. The documented translucent QWidget path on Windows would require changing to frameless behavior; that drag/resize/Snap/system-menu responsibility is not silently changed. See `windows-material-feasibility.md`.

## Safe review and evidence

Use `.local/SAFE-Pointer-Dual-v2-Preview.cmd`. Window title identifies **双区 v2 · 隔离预览**. This is source-only and opt-in: production entry, rejected experiments and previous ZIPs remain untouched. Backend operations are Mock and reject Apply/pause/resume/restore/startup; updater callbacks and service calls remain isolated. It reads no saved user configuration and does not persist preferences. No new package or push accompanies this candidate.

Private evidence `.local/dual-v2/` contains `pages/` (48 actual Qt captures at 880×620, 1180×880, 1800×900; both themes/pages, scroll, dirty, focus, 64 px), `custom-64/` (six expanded/top/bottom/focus views at 880), `dialogs/` (60 four-palette confirmation/button-state captures) and native hidden capability checks. These are app-owned widget captures, not desktop screenshots. Screenshot/geometry inspection is separate from test success and from final user aesthetic acceptance.

Seven new tests cover both pages at all widths, no horizontal clipping after Qt's queued responsive relayout, independent right scrolling, real family/palette/history/custom draft behavior, four confirmation theme combinations/default cancel, updater isolation, exact cached cursor pixels and 64 px containment, and press cancellation without reactivation. Existing motion golden/original resource tests remain authoritative. Full suite: 201 tests run, 200 passed and one skipped. The live-timer whole-window regression checks cursor/text layers after theme changes and resizing; frozen offscreen captures render the child widget before the parent snapshot. Thirty composed appearance captures also assert visible cursor pixels. Final counts/hashes are in `.local/dual-v2/delivery.json` and `sha256.json` after the run completes.
