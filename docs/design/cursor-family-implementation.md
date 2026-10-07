# Pointer B 构图：第一阶段运行候选

Historical stage: the P2 freeze below applies to the preserved family-candidate binary. Current source continues the separately authorized commercial reconstruction; see [current implementation](commercial-workspace.md).

日期：2026-10-06。基线：DEV `3511e3ea486d9e897ff752b2d0ee2e19e369e884`。

用户已结束原开发会话并授权接手推进。本阶段在已批准的 B 基础构图内实现 Qt 外观页候选：中左主角色与浅弧辅助角色、右上配对背景、左下统一外观、右下背景适配与高级编辑入口。v4 浅/深色图已实际查看，用作精修参考；不扩大为最终视觉批准。没有重新选择 A/B/C，没有生成替代设计图。

## 实际实现

- 全局草稿状态和应用操作移到稳定的顶右区域；运行状态仍独立显示。
- 17 个角色使用真实 cursor/art 渲染目录；选择角色或观察背景只影响预览，不写配置。
- 四造型、五档尺寸与背景适配更新草稿。八配色、自定义双态色值、光晕及颜色保留在可滚动的高级编辑窗口，主窗口显式应用。
- 界面明暗切换不写 CursorSettings。内部材质采用不透明表面，没有新增装饰动画。
- 切页、窗口失焦清理预览按下状态；原生 Qt 焦点与控件键盘操作保留。
- 放大渲染使用固定静止轮廓边界，保留各动画帧的坐标原点，避免动态裁切抵消按下位移。
- 1180×800 参考窗口；880×620 外观页可滚动到全部控件，全局 Apply 不随页面滚动。其他页面暂保留既有配色与功能，尚未整体迁移到 B 的视觉体系。

## 行为边界

配置、动效及 shake/game/tray/autoupdate 保持草稿→预览→显式应用。startup、pause/resume 沿用 application 即时事务。导入和默认设置进入草稿；导出当前草稿；原光标恢复维持现有明确确认。

application、Windows 光标备份和启动注册逻辑未修改。已有备份不覆盖，未变化启动项不重写，应用失败保留草稿及错误。新增布局不直接调用注册表或应用系统光标。

## 审阅与复现

隔离预览入口：`.build-env/Scripts/python.exe scripts/capture_family_ui.py --show`。该窗口使用隔离后端，不创建托盘、不自动检查更新、不应用系统设置。它用于界面审阅，不代表系统事务验证。

截图复现：`.build-env/Scripts/python.exe scripts/capture_family_ui.py`，仅使用 `window.grab()`，产物位于 ignored `.local/family-ui/`，包括浅/深色的 1180×800 与 880×620。

验证：`.build-env/Scripts/python.exe -m unittest discover -s tests`，最终运行 127 项，通过，1 项安装集成检查未启用。候选包用已有 build_release 的项目内 output_root，输出 `.local/family-candidate/`，跳过安装器，保留历史 dist。打包日志、最终测试和 diagnose 记录位于 `.local/`；打包诊断结果以本轮交付报告为准。

未测试实际键鼠/物理 DPI、安装升级、真实系统光标切换及 startup 注册。离屏截图没有系统窗口标题栏，不是整个桌面截图。细化材质、辅助角色光学权重、尺寸工具呈现和其余页面统一仍待视觉审阅；用户未最终批准所有 v4 细节。无 commit/push/merge/Release。


## Current implementation: selected-region polish and inline color editing

The earlier first-stage details and 127-test result above are historical. The current working tree continues the authorized B composition on DEV 3511e3e. B's base composition is approved; v4 image artifacts remain visual references rather than final acceptance.

| Before | After | Why |
| --- | --- | --- |
| Palette opens an extra editor window with duplicated controls | Eight presets on the appearance page; inline four body/outline colors and glow enable/color, HEX/RGB validation, local paired draft previews and undo | Keep edits and global Apply in the same workspace |
| Legacy advanced_dialog reference survives after editor removal | MainWindow enables the actual family page; no palette dialog or extra completion step | Restore window construction and one draft/Apply contract |
| Light preferences inherit dark-only labels and off-switch paint | Shared semantic Qt colors, readable primary/secondary text, visible off/on tracks, shorter truthful copy and wrapped rows | Make light and dark settings usable |
| Dark drag/wait pads retain black text | Explicit surface/text pairs; quieter test-page hierarchy; original light/dark/grayscale surfaces and 17 roles retained | Preserve real testing while making labels readable |
| Small role glyphs have uneven visual sizes/baselines | Actual renderer alpha bounds fitted into common optical frames; stronger main specimen, no renderer/hotspot edits | Clarify the family hierarchy without changing cursor geometry |
| Theme button and navigation mix selection with focus | Explicit switch-to-light/dark action; common 36 px header hitboxes; high-contrast selection and separate keyboard-only focus | Distinguish state, action and input modality |
| Header logo loads a low-resolution ICO pixmap | QIcon requests a 32 logical-pixel frame at device DPR from the existing identity asset | Improve icon sampling without inventing a new brand |

Hiding a focused color input can emit editingFinished. The reset transition now blocks that signal so stale text cannot overwrite a just-applied or discarded draft. Tests cover valid HEX/RGB, malformed/out-of-range input, discard plus focus loss, successful Apply ending the undo session, independent role/background observation, all 17 renderer previews and narrow-window field/Apply reachability.

Pre-P2 full suite: `.build-env/Scripts/python.exe -m unittest discover -s tests`, 135 tests, OK, 1 installation integration test skipped. Current local-only evidence: `.local/design-review/before/` and `after/`; screenshots include both themes at 1180x800 and 880x620, inline palette, hover, keyboard focus, dirty/error/disabled states and long Chinese copy. Actual rendered pixels were viewed. The regression failure log before the focus-transition fix is retained at `.local/design-review-unit-before-focus-fix.log`; the final run is `.local/design-review-unit.log`.

Targeted contrast report: `.local/design-review/after/contrast.json`. Primary/secondary settings text: 7.38-16.07:1; drag labels: 11.90-13.84:1; selected navigation: 6.95-11.45:1; keyboard focus token boundary: 6.95-9.32:1; actual painted off-switch track against its surface: 3.46-4.36:1. This measures named palette pairs and painted switch pixels, not complete application accessibility or physical-display calibration.

Candidate: `.local/family-candidate/dist/Pointer/Pointer.exe` and versioned ZIP. It is built with existing dependencies and skips the installer. Use `.local/SAFE-Pointer-UI-Preview.cmd` or `.build-env/Scripts/python.exe scripts/capture_family_ui.py --show` for an isolated mock-backend review; the ordinary packaged EXE connects to the real application backend. Do not confuse these entry points.

No actual system Apply, registry/startup changes, installation/upgrade, physical input/DPI test, Library upload, commit, push, merge or release. Application/backup/startup business logic is unchanged. Independent visual critique and user acceptance remain separate from this implementation verification.

Pre-P2 candidate --diagnose: exit 0, frozen true, Qt 6.11.2, 34 cursor resources including 4 animated, 32 click resources, 256 packaged files. Report: `.local/family-candidate-diagnose.json`. ZIP SHA-256: `e231083f6a1f45059ee4ad3e9221382ac41b20f2d00ef048c49381a92e5e2a69`.


## Final P2 follow-up and freeze

The parent reported that independent visual critique of the before/after images found no P0/P1 issues within this stage and requested only two P2 follow-ups. No broader module work was added.

- FamilySurface now paints a keyboard-visible focus ring using the token for its actual background. Space press/release feeds the existing preview set_down path. Auto-repeat does not create or release a new press. Focus loss, hiding/page changes, window deactivation and ungrab clear transient presses. Renderer, hotspot and system motion behavior are unchanged.
- FamilyComboBox retains the original Qt model/menu and draws a small readable theme chevron. Roles, observation background, size and adaptation remain the existing combo controls.
- Event-level regressions exercise Tab focus, Space press/release, auto-repeat release, blur and page change. Actual Qt images check focus-ring pixels on both UI themes and paired light/dark surfaces, plus disabled switch border pixels in both themes.
- `.local/design-review/after/p2-evidence.json` records actual disabled-switch samples, focus state, key press/release state, 17 role items, the last `person` item visible and horizontal-scroll maximum 0 at 880 width. The corresponding menu and surface screenshots were actually viewed. The harness activates only its own offscreen Qt window; it does not exercise physical keyboard input or machine display DPI.

Code is frozen for this stage. The safe preview remains `.local/SAFE-Pointer-UI-Preview.cmd`, using the isolated mock backend. Real input/DPI, install/upgrade and actual system Apply remain untested; no commit/push/upload was performed.

Frozen P2 state: full unittest suite 139 tests, OK (1 installation integration skip). Final candidate --diagnose exit 0, Qt 6.11.2, 34 cursor resources / 4 animated / 32 click / 256 packaged files. Final ZIP SHA-256: `ad7b9220064c619e7fbfd1d3996bcb4d62247d611982099d603340976879e372`. Final logs remain `.local/design-review-unit.log`, `.local/family-candidate-build.log`, `.local/family-candidate-diagnose.json`.
