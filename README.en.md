<div align="center">

# Pointer
### A clearer cursor. A more personal desktop.

Adaptive Windows cursors · Black & white contrast · Click motion · Reversible setup

[**Download installer**](https://github.com/ReactionForge/Pointer/releases/download/v1.3.0-beta.6/Pointer-v1.3.0-beta.6-setup-x64.exe) · [Portable ZIP](https://github.com/ReactionForge/Pointer/releases/download/v1.3.0-beta.6/Pointer-v1.3.0-beta.6-windows-x64.zip) · [简体中文](<README.md>)

![Pointer](<docs/media/cover.png>)

</div>

Pointer is a Windows 10/11 x64 desktop utility that adapts your system cursor to nearby light and dark backgrounds. Customize the shape, size, body and outline colors; preview changes before applying them.

## Highlights

- **Contrast that follows you:** black with a white outline on light backgrounds, white with a black outline on dark backgrounds by default. Fixed color modes are also available.
- **A complete cursor set:** 17 Windows cursor roles, including animated loading cursors. App-drawn cursors may not be replaced.
- **Tactile click feedback:** adjustable tilt and shrink motion with exact numeric controls; motion can be disabled.
- **Safe drafts:** changing a preview does not change Windows until you apply. Window appearance and cursor settings are separate.
- **Reversible:** preserves your original cursor backup, supports pause and restore, and keeps startup preferences through upgrades.
- **Local core functionality:** no account, Python installation or connection required for cursor features. Optional update checks and downloads contact GitHub.

![Current appearance page](<docs/media/app-appearance.png>)

Screenshots render the actual MaterialWindow in isolation. They are not live Windows compositor captures or proof of backdrop-blur behavior.

[Watch/download the 50-second demo](https://github.com/ReactionForge/Pointer/releases/tag/v1.3.0-beta.6) · [Reproduce the promotional assets](<docs/media/README.md>)

## Getting started

1. Install the EXE, or extract the entire ZIP and open `Pointer.exe`.
2. Customize your cursor and compare light/dark previews.
3. Select **应用更改** (Apply changes), then **光标测试** (Cursor tests) to inspect Windows cursors.
4. Use **应用设置** (App settings) to pause or restore the original cursors. Closing the window leaves the background effect running.

The interface is primarily Chinese. The ZIP deploys the application to a persistent user directory on first successful application; it is not a zero-write portable mode. Configuration and backups live in `%LOCALAPPDATA%\Pointer\data`, with the application in the adjacent `app` directory.

## Release status and limits

**v1.3.0-beta.6 remains a prerelease**, even after its source baseline is promoted to `main`. The previous stable v1.1.1 remains available. Users of beta.3 should manually install beta.6 once to obtain the update-check fix. Packages are currently unsigned: verify the GitHub source and SHA-256 rather than disabling Windows protections.

True backdrop blur requires a supported Windows 11 compositor environment. Windows 10, accessibility settings, disabled transparency and inactive windows use fallbacks. Mixed DPI, multi-monitor transitions, Snap, live high-contrast changes and long-running GPU/power behavior still need additional hardware validation. Non-default cursor generation can take time.

[Release checks and limitations](<docs/releases/1.3.0-beta.6.md>) · [Download and checksum guide (Chinese)](<docs/getting-started.md>) · [Support](<SUPPORT.md>)

## Development

Windows x64, Python 3.13:

```powershell
python -m venv .build-env
.\.build-env\Scripts\python.exe -m pip install -r requirements/dev.txt
.\.build-env\Scripts\python.exe -m pip install --no-deps -e .
.\.build-env\Scripts\python.exe -m unittest discover -s tests
.\.build-env\Scripts\python.exe -m pointer --gui
.\.build-env\Scripts\python.exe -m scripts.build_release
```

[Contribution and build instructions](<CONTRIBUTING.md>) · [Architecture](<docs/architecture.md>) · [Security](<SECURITY.md>) · [Data and privacy (Chinese)](<PRIVACY.md>)

## Rights and commercial readiness

Public source visibility is **not** a general open-source or commercial redistribution license. Ownership and commercial rights for historical project assets have not yet been confirmed by the maintainer. No MIT license has been added. Qt/PySide and other dependencies retain their own licenses and obligations.

This is a publishable beta repository and promotional package, not a completed legal clearance, code-signing or full hardware certification. See the [commercial readiness checklist](<docs/commercial-readiness.md>) before selling or redistributing a derivative.

## Share responsibly

Star the project, share the demo or report a reproducible compatibility issue. There are no fabricated endorsements, performance promises or guaranteed popularity. [Launch copy and distribution plan](<docs/launch-kit.md>) · [Issues](https://github.com/ReactionForge/Pointer/issues)
