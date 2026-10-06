# Pointer

<!-- impeccable:product-schema 1 -->

## Platform

Windows desktop, implemented with Qt Widgets. This is a native Windows application; web, iOS, and Android are not its shipped platforms.

## Users

Windows users who want to personalize their system cursors and evaluate their appearance and behavior before applying a configuration.

## Product Purpose

Configure adaptive cursors, adjust left-click motion, preview drafts, and test the actual Windows cursor. Installation, configuration, and restoration should be understandable without technical knowledge.

## Operating Context

The desktop app is downloaded from GitHub. Configuration and cursor generation work locally. The settings window and background cursor service are separate processes. The existing web test page remains a development aid.

## Capabilities and Constraints

- Preserve the existing cursor styles, palettes, motion modes, theme and JSON import/export, startup choice, tray controls, update flow, and system cursor tests.
- A preview uses the draft. Actual system tests use the applied Windows cursor. Changing a draft must not modify the system.
- Explicitly applying settings performs the existing application transaction. Preserve the original cursor backup and avoid rewriting an unchanged startup entry.
- Existing implementation: Python 3.13, PySide6-Essentials Qt Widgets, Pillow, PyInstaller, Inno Setup. No WebEngine or browser service in the shipped app.
- Develop and push to DEV. Do not merge main or create release tags without a publish request.
- Private machine state and diagnostic captures belong in ignored .local/.

## Brand Commitments

- Retain the Pointer name and its existing cursor identity.
- The user explicitly requested an Apple software family visual direction on 2026-10-06. Interpret this through hierarchy, spacing, grouped settings, and interaction quality while preserving Windows window controls and keyboard behavior.
- Preserve the user's adaptive cursor colors: black body with white outline on light backgrounds, white body with black outline on dark backgrounds. Preserve the absence of cursor glow in their chosen configuration.
- User-facing copy is primarily Chinese, concise, and concrete. Describe effects and choices without implementation jargon or unverified performance claims.

## Evidence on Hand

Existing UI source under src/pointer/ui/, test source under tests/unit/ui/, design and architecture documentation under docs/, and current cursor assets under assets/cursors/. Current behavior is the product truth; older screenshots and design documents may predate later features.

## Product Principles

1. Preview safely before applying.
2. Make the current system state and draft state distinguishable.
3. Keep normal tasks easy and advanced controls available.
4. Preserve recoverability and user startup choices.
5. Prefer coherent native desktop interactions over decorative complexity.
