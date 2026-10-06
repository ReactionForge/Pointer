# Pointer UI design direction

Status: revised visual proposal on 2026-10-06. The user rejected the first flat, grouped-settings concepts as too similar to the existing application. Apple software family remains confirmed; the revised compositions require visual review before product implementation.

## Visual world — Liquid Focus

Translate Apple's material hierarchy and interaction precision into a Windows cursor workspace. The preview occupies the main canvas; navigation and contextual controls form a separate functional layer. Keep Pointer's identity, Windows window behavior, and the existing rounded black-and-white cursor geometry.

The signature is an expansive dual-background cursor stage with a lightweight translucent functional layer around it. Glass belongs to navigation, compact toolbars and transient controls. The stage, form content and readable labels use opaque or sufficiently tinted surfaces. No wallpaper imitation, ornamental glass cards, cursor glow or Apple branding is needed.

Apple references: [Materials](https://developer.apple.com/design/human-interface-guidelines/materials), [Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/liquid-glass), [Motion](https://developer.apple.com/design/human-interface-guidelines/motion), and the [official macOS interface examples](https://www.apple.com/newsroom/2025/06/macos-tahoe-26-makes-the-mac-more-capable-productive-and-intelligent-than-ever/). These establish reference principles; Pointer's workspace and timings below are our proposed adaptation.

## Layer hierarchy

1. Content: a clean pearl or graphite canvas, large cursor specimens, real setting labels and scene content. The cursor remains a flat accurate specimen rather than a decorative 3D object.
2. Functional surface: a floating sidebar or toolbar with a translucent softly tinted fill, an optically aligned icon family, a fine light edge and a soft directional shadow. It separates navigation from content without fogging text.
3. Transient surface: a contextual popover or apply feedback anchored to its trigger. One elevated interaction at a time; avoid glass nested inside glass.

On Windows use Qt-drawn internal surfaces and a restrained optional native backdrop behind navigation. Materials must remain coherent with an opaque fallback, reduced transparency, or unsupported compositing. Do not promise Apple's proprietary rendering on Windows or use a static screenshot as the running interface.

## Type, geometry and density

- Windows-installed Segoe UI Variable / Segoe UI and Microsoft YaHei UI fallback. Do not bundle SF Pro.
- Title 28 logical px, section 16 semibold, control labels 14, supporting text 13. Values use tabular figures and explicit units.
- Spacing rhythm: 4 / 8 / 12 / 16 / 24 / 32. Related controls are close; task groups have generous separation. Refine optical alignment.
- Content radius 20–24; floating rails 20; preview stage 24; control groups 12; pill shapes for compact tools only. Nested curves are concentric with radius reduced by inset.
- Minimum comfortable target 32 logical px; prominent actions 36–40. Independent visible keyboard focus. Thin dividers and grouped rows replace repeated outlined cards.

## Semantic palette

| Role | Light | Dark |
| --- | --- | --- |
| Canvas | #F6F6F8 | #191A1E |
| Content surface | #FFFFFF | #25262B |
| Functional opaque fallback | #EBECF0 | #303137 |
| Functional highlight | #FFFFFF | #686A73 |
| Primary text | #202126 | #F5F5F7 |
| Supporting text | #5D5F68 | #B2B5C0 |
| Divider | #DBDDE3 | #494B55 |
| Selected control | #E7EFFB | #294469 |
| Accent / primary action | #0064D8 | #0064D8 |
| Focus | #0064D8 | #8DBBFF |
| Success | #16683D | #86DEAF |
| Error | #B42318 | #FFADA7 |

The default cursor contrast is separate from interface colors: light background black body/white outline; dark background white body/black outline; glow off. Preserve existing custom palettes and optional glow controls under advanced settings.

## Interaction language

- Mouse selections update data and previews immediately. A subtle selected capsule may catch up over 140–180 ms; page content does not wait or fly in.
- Buttons compress to 0.98 on mouse press over 80 ms and return over 140 ms without shifting layout or the hit target. Keyboard actions give immediate feedback.
- Sliders track input directly; the value stays visible and a temporary value bubble can follow the thumb. No spring on the value or artificial cursor lag.
- Popovers grow from their trigger from 0.98 to 1 with restrained opacity over 160 ms. Anchors and opening directions remain stable at window edges.
- Apply keeps its width and location while changing from action to progress to result. Report success only after the real operation finishes. Errors persist with retry; drafts survive.
- UI motion stays independent of system cursor motion. Interruptions retarget from the current value; focus loss resets transient press state. Reduced motion and transparency have deliberate fallbacks.

## Revised composition probes

All three use the same Liquid Focus world, product features and cursor contrast. They vary workspace structure.

- A — Focus workspace: translucent left navigation, generous central preview stage, slim contextual inspector on the right. Recommended for preview persistence and stable apply action.
- B — Gallery workspace: floating top navigation, wide comparison stage, shape specimens and horizontal inspector. More visual discovery, fewer controls visible at once.
- C — Compact studio: narrow navigation rail, left inspector, full-height preview canvas on the right. More immersive comparison with a denser settings column.

The first-round images are superseded. New proposals use apple-v2-*.png. They are design mockups, not screenshots of implemented software. Generation prompts and human approval state remain in .impeccable/mocks/; public proposal context lives in docs/design/.
