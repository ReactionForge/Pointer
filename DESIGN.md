# Pointer UI design direction

Status: DEV version 1.3.0-beta.3 uses the user-approved Material workspace as its desktop entry. Navigation, rounded content, the fixed Apply footer and original motion baseline are preserved. Sidebar opacity and native host-backdrop Gaussian blur are independent, with an opaque fallback. The latest controls use a light slider treatment and an explicit light/dark theme selector. See [release validation](docs/releases/1.3.0-beta.3.md) for actual evidence and remaining limits. The dual-workspace and earlier vertical candidates below are design history; publication is gated by the Windows release workflow.

## Visual world — Liquid Focus

Translate Apple's material hierarchy and interaction precision into a Windows cursor workspace. The preview occupies the main canvas; navigation and contextual controls form a separate functional layer. Keep Pointer's identity, Windows window behavior, and the existing rounded black-and-white cursor geometry.

The signature is a responsive cursor workspace: the selected role, comparison background and relevant controls relate directly, instead of occupying three equally weighted fixed columns. Contrast comes from a dominant specimen, smaller supporting roles, real scene content and deliberate asymmetric space. Glass belongs to navigation, compact toolbars and transient controls. Content and readable labels retain stable surfaces. No ornamental glass, cursor glow or Apple branding is needed.

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
- The workspace responds to intention: role selection focuses the chosen specimen; a comparison divider follows dragging immediately; an inspector changes its controls in place. Main navigation, apply action and keyboard anchors remain stable. No automatic orbit, idle breathing, magnetic cursor or drifting controls.
- Asymmetric composition carries focus without implying unequal contrast importance. Every preview labels its background, draft status and scale. Scene content supports the task; it does not claim that a draft has been applied to Windows.

## Approved composition and refinement

The user selected B from the third round. Its approved base is docs/images/apple-v3-b.png; A and C remain exploratory references, not implementation choices. Refine this composition without replacing its material world or reorganizing its primary regions.

- A — Living canvas / 流动舞台: expansive asymmetric light/dark stage, draggable comparison boundary, compact horizontal instrument shelf and a stable top action. No tall inspector or sidebar.
- B — Cursor family / 光标家族: one dominant selected role and smaller related role specimens in a shallow fan, with a compact contextual inspector and common style controls. Ordered selection remains available with keyboard navigation.
- C — Scene atelier / 情境工作台: a large image interaction scene balanced by compact text and click scenes, a stable task dock and an expandable contextual shelf. Real preview content creates rhythm; each scene remains clearly marked as a draft.

Refinement targets: normalize optical weight of the supporting role glyphs; preserve a dominant selected role; clarify preview background selection separately from system adaptation; use a real-size specimen alongside the configured size; reduce redundant borders in the shared appearance shelf; preserve stable navigation and apply anchors in light and dark states.

The preview mode defaults to comparison when both light and dark specimens are visible. System adaptation remains a separate automatic/light/dark control. Selecting a role changes the preview only, while appearance settings stay shared. Keep all existing shapes, palettes, motion, startup, recovery and testing functions available.

Approved direction is distinct from finished software. Images remain design artifacts; human approval scope lives in .impeccable/mocks/ and the public layout provenance. Refined screenshots use apple-family-v4-*.png and do not imply that animation or Windows cursor behavior has been implemented or verified.
