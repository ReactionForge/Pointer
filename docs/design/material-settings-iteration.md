# Material 设置与测试页迭代

本轮在现有 Material v2 候选上增量修改。设置与测试页已经实施；**可调背景毛玻璃尚未完成 Qt 集成，不能作为已完成项验收**。保留 DEV 分支及进入本轮前的未提交成果，没有提交、推送、合并或发布。

## 启动与范围

- 当前安全入口：`.local/SAFE-Pointer-Material-v3-Preview.cmd`，运行 `scripts/preview_material_settings.py`。实际启动检查通过。
- 原入口 `.local/SAFE-Pointer-Material-v2-Preview.cmd` 保留，其 `--show` 也接入独立外观存储。
- 交付为源码安全预览，没有生成本轮新 Windows 发行包。
- Mock 后台阻止应用、恢复、暂停、启动光标及启动项操作；更新服务隔离。未实际更换系统光标、修改 Windows 全局透明或无障碍设置。
- 外观存储位于忽略目录 `.local/material-v3/sidebar.json`。验收后恢复默认值：开启透明，深色 alpha 184，浅色 alpha 208，blur 0。

## 已实施

标题栏的透明选项移到设置页“侧栏外观”。透明开关和透明度提供即时预览、明确的保存和取消操作，深浅主题透明值独立保存，重启加载。窗口外观草稿独立于系统光标配置；未保存关闭时使用现有主题适配确认框，两类草稿同时待保存时只询问一次。

前景文字与图标维持正常绘制，右侧内容和底部操作条保持不透明。透明关闭、失活、系统透明关闭、DWM 合成关闭、不支持或高对比时使用不透明回退，保留用户保存的选择。通过只读系统查询、窗口激活及系统通知刷新策略，没有修改系统偏好。

测试页采用“背景适配”“点击与拖动”“输入与加载”三个局部标签。深浅背景、灰度滑块、数值及六个色块集中排列；点击计数和状态减弱；宽窗输入与加载并排，窄窗顺序排列。保留手型、按下反馈、拖动、文本输入、加载模拟及 17 种角色目标。切换分组或隐藏页面结束临时状态，测试交互不产生配置待应用状态。

## 正式 Composition 原型结果

原型仅在 `.local/material-v3/composition-probe/`，使用系统已有 .NET Framework 编译器、WinRT 元数据和现有 Python/Qt；没有安装工具、新增项目依赖或使用桌面截图作为背景输入。

原生 `WS_EX_NOREDIRECTIONBITMAP` 窗口通过 DispatcherQueue、Compositor、DesktopWindowTarget、host backdrop brush 和 Gaussian 效果工作。同样的视觉 opacity 1、无染色下，sigma 0 与 24 DIP 的实际桌面截图有不同模糊程度。保持这些参数与效果窗口位置不变，将真实背后窗口拖动后，效果窗口内的模糊背景随之更新；配对截图和坐标记录见 `composition-move-before.jpg`、`composition-move-after.jpg`、`composition-move.json`。host backdrop 本身已平滑，0 表示不增加这层 Gaussian，并不表示无任何背景平滑。原型自己的前景控件没有成功显示，因此不能将该原型判为完整产品实现。

绑定到现有 Qt 顶层 HWND 后，正式效果成功激活，但覆盖了 Qt 光栅前景。`isTopmost=false` 仅将效果树放在子 HWND 下方，普通 QWidget 共用顶层 backing store，其文字仍被遮盖。原生父窗口加 Qt 子窗口的两个尝试也没有通过：原始 reparent 丢失 Qt 前景；使用 Qt 支持的 foreign-window parenting 恢复前景却改变 layered 样式，背景保持清晰、布局缩放及裁剪异常。

因此当前“背景模糊”控件禁用，明确标注“未启用”，不会将透明度或染色强度冒充模糊度。可行的后续方向是正式 Composition 宿主加独立 Qt 前景合成桥接，或支持 Composition 前景的渲染路径；需要进一步验证 HWND 生命周期、透明、DPI、裁剪、输入和失活。`CreateSurfaceFromHwnd` 是待评估路线，本轮没有实现或验证。

依据：[Microsoft host backdrop](https://learn.microsoft.com/en-us/uwp/api/windows.ui.composition.compositor.createhostbackdropbrush?view=winrt-26100)、[Gaussian 参数](https://learn.microsoft.com/en-us/windows/win32/direct2d/gaussian-blur)、[效果树层次](https://learn.microsoft.com/en-us/windows/win32/api/dcomp/nf-dcomp-idcompositiondesktopdevice-createtargetforhwnd)、[layered HWND surface](https://learn.microsoft.com/en-us/windows/win32/api/dcomp/nf-dcomp-idcompositiondesktopdevice-createsurfacefromhwnd)。详细原型日志和限制见 `.local/material-v3/composition-probe/README.md`。

## 验证与证据

- `.build-env/Scripts/python.exe -m unittest discover -s tests`：226 项，225 通过、1 项跳过，130.636 秒。完整输出 `.local/material-v3/full-tests.log`。
- 已有动效恢复包执行 `--diagnose`：exit 0，frozen true，256 package files；输出 `.local/material-v3/packaged-diagnose.log`。此结果仅覆盖旧包，不能证明本轮源码已打包。
- 保留清单检查 429 个资源、基线和归档文件，未改变或缺失；36 个原始资源、640 项原始像素/热点基线、56 个 ZIP 的哈希保持原样。没有重录基线，未改原始圆润动效实现。
- 原生窗口操作：透明保存后关闭再启动恢复；取消预览恢复已保存值；深浅主题的关闭确认继续编辑；滑块方向键；滚轮经过滑块数值保持不变；测试点击和拖动；加载区进入后离开结束；局部标签方向键切换；920×680 窄窗滚动；最大化及还原。上述测试交互后均显示“无待应用更改”。
- 布局检查矩阵额外覆盖深浅主题、3 个分组、880 与 1180 两种宽度；该矩阵为 Qt 内部渲染，仅用于布局，不能用作桌面毛玻璃证据。

实际桌面截图位于 `.local/material-v3/native/`，交付前逐张查看。主要文件：

| 文件 | 证据 |
| --- | --- |
| `settings-dark-off.jpg` | 深色设置、透明关闭与已保存状态 |
| `settings-narrow-light.jpg` | 浅色窄窗设置，模糊明确禁用 |
| `tests-background-narrow-light.jpg` | 深浅背景与紧凑灰度区 |
| `tests-click-drag-dark.jpg` | 实际点击与拖动后的低干扰状态 |
| `tests-input-wide-dark.jpg` | 宽窗输入与加载并排、固定操作条 |
| `tests-input-narrow-light.jpg` | 窄窗输入与加载顺序排列 |
| `tests-input-scrolled-light.jpg` | 滚动、角色目标与固定操作条 |
| `tests-maximized-dark.jpg` | 最大化后的布局 |
| `close-confirm-dark.jpg`、`close-confirm-light.jpg` | 两种主题的未保存确认 |
| `composition-0-24-revised.jpg` | 原生隔离原型不同 sigma 的真实桌面效果 |
| `composition-move-before.jpg`、`composition-move-after.jpg` | 固定效果窗口和参数下，背后真实窗口移动的前后桌面证据 |
| `qt-layered-topmost.jpg` | Qt 前景被覆盖的失败证据；文件名历史沿用，实际 target 参数为 false |
| `host-qt-foreign-parent.jpg` | Qt 前景恢复但背景无有效 Gaussian 的失败证据 |

## 未验收项

当前应用的可调背景模糊、不同模糊值下前景清晰以及完整 Qt 背景实时移动合成均未通过，不能宣称毛玻璃完成。高对比/系统策略关闭等回退通过注入策略测试，未修改真实 Windows 设置进行切换；混合 DPI、跨屏、Snap、鼠标边缘调整大小及本轮新发行包未验收。
