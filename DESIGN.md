# Pointer UI design direction

Status: Apple software family direction confirmed by the user on 2026-10-06. The screen compositions and interaction changes below are proposals pending visual review.

## Visual world

Use an Apple-inspired desktop utility language: quiet neutral surfaces, grouped settings, precise typography, restrained depth, and immediate feedback. Keep the actual Windows title bar and platform interactions. Pointer remains the brand; do not add Apple logos, false macOS window controls, or marketing claims.

The subject is the cursor. Its actual geometry and black/white contrast should be the visual focus. Expression lives in the preview, alignment, and control craft rather than ornamental backgrounds.

## Type and spacing

- UI: Windows-installed Segoe UI Variable / Segoe UI and Microsoft YaHei UI. Do not package proprietary Apple fonts.
- Normal labels: 14 logical px; supporting text: 13 logical px; section labels: 15 px semibold; page titles: 25 px semibold. Use actual Qt font metrics and scale for Windows DPI and font settings.
- Base rhythm: 4, 8, 12, 16, 24, 32. Grouped panels have 16 px inner spacing, 12 px corner radius, and one subtle boundary treatment. Main content gutters: 24 px.
- Numeric values use tabular figures when supported; labels remain in the normal UI family.

## Proposed semantic colors

| Role | Light | Dark |
| --- | --- | --- |
| Window | #F5F5F7 | #1C1C1E |
| Sidebar | #ECECEF | #252527 |
| Panel | #FFFFFF | #2C2C2E |
| Elevated panel | #FFFFFF | #363638 |
| Primary text | #1D1D1F | #F5F5F7 |
| Secondary text | #626268 | #B0B0B7 |
| Hairline | #DEDEE3 | #48484C |
| Selection | #E6F0FF | #203957 |
| Primary action fill | #0066CC | #0066CC |
| Selection text / focus | #0066CC | #76BBFF |
| Success text | #16703C | #70D997 |
| Warning text | #875200 | #FFD083 |
| Error text | #B42318 | #FF9B92 |

Use the accent for selected controls, keyboard focus, and primary actions. Cursor glow remains controlled by the user's cursor configuration and is not implied by the interface's accent color.

## Component character

Use one icon family with consistent 1.5–1.75 px strokes. Use semantic Qt buttons, checkboxes, sliders, spinboxes, and combo boxes, with accessible names and visible focus states. Styling must cover hover, press, selected, disabled, busy, and error states in both themes.

Prefer concise grouped rows to nested cards. Advanced color and optional glow controls remain reachable through disclosure. A selected cursor style or preset exposes a check and a border, not color alone.

## Motion grammar

Pointer's cursor animation is an existing configurable feature and stays independent of interface motion. Proposed UI timings: press feedback 100–140 ms, toggle transition 140–180 ms, transient feedback fade 160–200 ms. Keyboard navigation is immediate. No page entrance choreography. Retarget interrupted feedback from its current state. Reduced interface motion uses immediate state changes and restrained opacity feedback.

## Composition alternatives

1. **A — 分栏设置**: left navigation, grouped settings in the center, persistent draft preview on the right, and a stable bottom action bar. Proposed recommendation for the desktop app.
2. **B — 预览工作区**: top navigation, a large dual-background preview leading the screen, and a compact inspector below. Stronger visual focus, with less configuration visible at once.
3. **C — 紧凑设置**: left navigation, inline dual-background preview, and grouped settings across the full content column. Favorable for narrower windows, with less preview persistence while scrolling.

The user pinned Apple software family style, so the concept seed's alternate material worlds cannot replace it. They contribute only task-relevant discipline: tonal contrast, stable grids, clear selection, and persistent change state. The seven considered sources span editorial spacing, product-photo staging, specimen grids, photographic contact sheets, software identity, typographic hierarchy, and measured motion. The selected third source (specimen-grid precision) is translated into the existing native desktop controls and exact cursor previews; its exposed construction grid is omitted because it has no task purpose.

## Review artifacts

Visual concepts live under docs/images/. Their status is a proposal, not a screenshot of completed software. The design philosophy is in docs/design/apple-visual-philosophy.md. Detailed scope and interaction proposals are in docs/design/apple-ui-redesign.md. Final screen composition will be recorded after the user reviews the images.
