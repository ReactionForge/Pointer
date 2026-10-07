# Windows material feasibility — narrow preview experiment

## Result and scope

Local private evidence records Windows 11 build 26200 and Qt 6.11.2. The official DWM system-backdrop attribute is supported from Windows 11 build 22621. A newly created, hidden Pointer Mock preview window accepted `DWMWA_SYSTEMBACKDROP_TYPE=DWMSBT_MAINWINDOW` (38 / 2), read back 2, and restored its original 0. All HRESULTs were zero. The window kept its native frame, did not set `WA_TranslucentBackground`, did not show or activate, and executed zero system cursor operations. See `.local/material-feasibility/native-probe.json`.

This is proof that the supported Windows API accepts a material request for our own window. It is **not proof of visible Mica pixels**, and the content area remains opaque. QWidget captures do not contain DWM's non-client/title-bar composition; the hidden probe has no final on-screen material pixels to inspect. No desktop screenshot or wallpaper capture was made.

Mica is an opaque, system-composed wallpaper-derived background material, not the live translucent desktop blur requested by the reference. Windows Acrylic is the closer blur material, but Microsoft recommends it on transient surfaces and cautions against large desktop-acrylic backgrounds and unnecessary GPU cost. Neither a translucent stylesheet nor whole-window opacity provides Acrylic blur.

## Qt constraint

Qt 6.11's documented top-level translucent QWidget path on Windows requires `FramelessWindowHint`. We cannot use that path while preserving the existing native title bar and window behavior. Current QWidget backing-store/client surfaces paint opaque content over the DWM backdrop. Changing that rendering integration would require a separate compositor/window-host design and validation, not a small safe stylesheet adjustment. This does not establish that native-frame blur is impossible in all Windows frameworks; it limits what is verified in this existing Qt Widgets path.

No undocumented `SetWindowCompositionAttribute`/accent-policy hacks, alternate desktop-control APIs, registry writes, shell hooks, third-party package installation or screenshots-as-background were used.

## Optional isolated experiment

`.local/SAFE-Pointer-Material-Preview.cmd` opens a **separate** Mock preview; the existing layout-only SAFE entry is unchanged. In Settings its experimental native-window Mica switch is off by default. It requests only the documented DWM window attribute for this preview's own HWND; it does not make the content translucent or claim a sidebar glass effect. Switching off and accepting window close restore the previous attribute. OS cursor and updater operations remain blocked, and no user setting is persisted.

The candidate checks Windows build, Windows QPA, composition availability and read-only `SPI_GETHIGHCONTRAST` before requesting material. Unsupported platforms, query failures and high contrast keep the existing opaque client fallback. Native hidden tests confirmed readback on/off, restoration on close, unchanged draft and simulated high-contrast/older-platform rejection. Offscreen Qt disables the switch. These simulated checks do not constitute physically switching system accessibility settings.

Microsoft documents automatic Mica fallback when transparency is disabled, high contrast/battery saver is active, hardware is insufficient or a window deactivates. We delegate that behavior to DWM; actual system-transparency-off and battery-saver pixels have **not** been tested. The preview's opaque content and confirmation contrast are stable throughout. No repeated blur rendering or polling loop is introduced.

The honest near-term fallback is the current two-page compact layout with opaque light/dark levels, thin surface boundaries, readable text and native window controls. It is not the completed reference material effect. Broader client-material integration needs a separate decision after layout review; no production build or animation/Apply change accompanies this experiment.

## Official sources

- [DWM system backdrop types](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwm_systembackdrop_type)
- [DwmSetWindowAttribute](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/nf-dwmapi-dwmsetwindowattribute)
- [Qt 6.11 QWidget translucent windows](https://doc.qt.io/qt-6.11/qwidget.html#creating-translucent-windows)
- [Microsoft Mica behavior and fallback](https://learn.microsoft.com/en-us/windows/apps/design/style/mica)
- [Microsoft Acrylic material guidance](https://learn.microsoft.com/en-us/windows/apps/design/style/acrylic)

Supplementary layout evidence `.local/reference-ui-revision/custom-64/` covers 880 px custom colors expanded, scrolled and keyboard focused, in both themes. Normal single-panel scrolling is allowed; preview and Apply remain fixed. This evidence is separate from DWM pixel validation.
