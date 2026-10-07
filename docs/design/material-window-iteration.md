# Material 窗口、毛玻璃与布局迭代

> 这是 v4 源码安全预览的历史验收记录。后续正式入口、新包验证及发布范围见 [1.3.0-beta.2 验收记录](../releases/1.3.0-beta.2.md)。

本轮在现有 Material 实现上增量修复，不覆盖上一轮记录。分支仍为 DEV，保留进入本轮前的未提交改动，没有提交、推送、合并或生成发行包。

## 启动

使用 `.local/SAFE-Pointer-Material-v4-Preview.cmd`。入口运行 `scripts/preview_material_settings.py`，默认 1360×920，保留 `.local/material-v3/sidebar.json` 的已存外观；旧 v2/v3 入口及成果仍在。启动后设置页的“背景模糊”可调，0 表示关闭这层背景效果。

这是源码安全预览。后台仍是 Mock，应用、恢复、暂停、启动光标及启动项操作被阻止；更新检查、下载和安装隔离。没有更换系统光标，没有修改 Windows 全局透明度、高对比、安全或权限设置。没有安装工具或新增第三方包。首次运行使用电脑现有 .NET Framework 编译器和 Windows WinRT 元数据构建项目自带的小型 Composition helper；缺少环境或启动失败时给出原因并回退不透明。

## 修改

- 去掉单独的“Pointer · 安全预览”顶栏。页面标题与操作按钮在现有界面内，红、黄、绿按钮位于窗口右上角，支持关闭、最小化、最大化/还原、键盘焦点及原生系统菜单。
- 统一页面标题、卡片和底栏的对齐，清除导航容器残留的长竖线；收紧外观页双列间距，给滚动条独立留出 12 DIP 间隔，修复轨道默认棋盘填充。固定底栏采用状态与反馈两行，以及“取消 / 应用更改”。
- 窗口外壳统一绘制圆角，右侧与底栏保持不透明；普通窗口恢复四角圆角，最大化时使用方角。
- 动效选择无法切换的原因是主窗口边缘调整大小的过滤器处理了独立下拉弹窗的鼠标按下事件。现在只处理主窗口事件；选择框及弹窗选项使用手型指针。
- 顶部拖动区域覆盖页面标题、顶部留白及左侧 Pointer 品牌，排除窗口按钮和其它交互控件。优先调用原生窗口移动；平台拒绝时按全局鼠标位移回退，释放、隐藏和失活结束拖动。原生成功时不叠加手动移动。原实现只有 y22–57 的标题命中区，且原生失败后仍吞掉事件，没有回退。
- 透明度与模糊的滑轨起止一致，右侧数值列对齐；直接输入透明度 0–100% 或模糊 0–48，回车或失焦确认，并与滑轨双向同步。数值输入沿用禁止滚轮误改的控件；透明度百分比只映射侧栏 alpha，模糊值仍为独立 Gaussian 参数。
- 保留测试页“背景适配 / 点击与拖动 / 输入与加载”分组、全部测试功能和宽窄布局。测试操作不产生光标配置待应用状态。

## 实际背景模糊

正式实现位于 `src/pointer/windows/composition/` 和 `composition_host.py`。独立、禁止激活的原生窗口只绘制 Windows Composition 的 host backdrop + Gaussian；位于 Qt 前景窗口下方。Qt 不改变父窗口、owner 或样式，文字和图标继续正常绘制，不采集桌面图片作为背景输入，也不模糊控件。

滑块改变 Gaussian 的 StandardDeviation（DIP，0–48），透明度独立改变侧栏填充 alpha，不用染色浓度冒充模糊。0 时隐藏原生效果层，留下普通区域 alpha 透明。保存与取消、深浅主题透明度记忆、重启恢复沿用独立外观存储，不触发系统光标配置草稿。

helper 通过有界 UTF-8 JSON 行协议与 QProcess 通信，核对固定目标的 HWND/PID，串行确认状态，父进程或目标消失时退出。修复了 Windows 匿名管道延迟首次写入时 Console.ReadLine 阻塞的问题，改为读取自己的 stdin ReadFile，保留严格大小、编码、EOF 与零字节写入处理。错误、超时或几何读取失败时隐藏效果，保留用户参数并回退不透明；关闭确认选择继续编辑不会销毁 helper。

激活、移动、大小变化、最小化及系统策略通知同步几何和可见性。失活、关闭效果、高对比、系统透明关闭、合成不支持或 helper 失败时回退。100 ms 层级检查只调整 helper 本身，修复其他窗口插入 Qt 与效果层之间的情况，不抢激活、不重新显示已隐藏的 helper；该间隔不是逐帧或调度延迟保证。

当前机器已通过实机验证。host backdrop 的支持条件与失败原因详见私有原型记录；DWM host backdrop 属性要求 Windows 11 build 22000 或更新的受支持环境。依据：[Microsoft host backdrop](https://learn.microsoft.com/en-us/uwp/api/windows.ui.composition.compositor.createhostbackdropbrush)、[DWM 属性](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute)、[Gaussian 参数](https://learn.microsoft.com/en-us/windows/win32/direct2d/gaussian-blur)。

## 验证

所有交付截图均自行查看，发现滚动条棋盘纹后修复并重启复查。Qt 内部渲染只用于布局矩阵，以下 JPG 为实际 Windows 窗口/桌面合成截图。

最终数值框也经独立视觉复核，没有边界裁剪或遮挡。实际 JPG 的部分小字存在细笔画损失，离屏 PNG 中文字完整且更宽的“48”也未裁剪；现有证据更符合截图缩放/压缩失真，尚未单独定位具体截图环节。

| 验证 | 实际结果与证据（均在 `.local/material-v4/`） |
| --- | --- |
| 完整测试 | 最终源码执行 `.build-env/Scripts/python.exe -m unittest discover -s tests`：274 项，273 通过、1 跳过，210.356 秒；`full-tests-delivery.log`。跳过的是未配置 `POINTER_PACKAGE_ROOT` 的新包集成测试 |
| 最后轨道样式后的相关复测 | 23 项通过，68.925 秒；`final-material-focused.log` |
| 旧包 diagnose | 已有 `.local/motion-restored-final-candidate/dist/Pointer/Pointer.exe --diagnose --quiet --report …` exit 0；`packaged-diagnose.json`。只覆盖旧包，不能证明本轮新源码已打包 |
| 原始成果 | 起始清单 429 个文件，changed/missing 均为空；36 个原始资源、640 项原始像素/热点基线、56 个 ZIP 保持不变；`preserved-final.json`。没有重录基线，没有改原始圆润动效实现 |
| 模糊值实际区别 | `native/product-max-blur10-alpha140.jpg` 与 `product-max-blur48-alpha140.jpg`：相同 alpha 140、相同最大化窗口几何，10 与 48 背景平滑程度不同，前景清晰、右侧不透明。另有 blur0/24/10 对照 |
| 背后窗口真实移动 | `native/product-moving-before.jpg`、`product-moving-after.jpg`、`product-moving.json`：参数保持 sigma48/alpha140，真实背景 HWND 从 `[227,120,642,591]` 移到 `[-65,120,350,591]`，Pointer 持续激活，背景实时变化 |
| 新背景窗层级 | `native/final-noactivate-z-order.json`：新禁止激活测试窗打开后 foreground 仍为 Pointer，可见顺序 Qt→Composition helper→新背景窗；`final-background-insertion-maintained.jpg`。隔离 native 插入/隐藏/不抢激活回归见 `composition-probe/zorder-repair-evidence.json` |
| 保存/取消/恢复 | 实机保存 blur10 后关闭并重启恢复；键盘将24调为25，取消恢复10；关闭透明后侧栏不透明，取消恢复；`native/final-keyboard-blur-light.jpg`、`final-effects-off-light.jpg` |
| 直接数值输入 | 实机输入浅色透明度80%、模糊5，回车后滑轨分别同步为204/255与5，保存到独立验收文件；将5调为6再取消恢复5，关闭并重启仍为80%/5；切深色恢复该主题45%，模糊仍5。`native/final-numeric-saved-light.jpg`、`final-numeric-cancel-light.jpg`、`final-numeric-restart-light.jpg`、`final-numeric-settings-dark.jpg`。底部始终无待应用光标更改；输入/失焦/精度/轮滚/保存取消4项专门回归通过 |
| 关闭确认 | 深浅主题未保存确认、Escape继续编辑保留草稿，窗口失活时不透明，返回恢复模糊；`native/close-confirm-dark.jpg`、`final-close-confirm-light.jpg` |
| 动效下拉 | 实机逐一选择倾斜、缩小回弹、弹簧回弹、关闭；选择正确，关闭时相关控件禁用；弹窗点击/键盘/手型回归测试通过 |
| 深浅/窄窗/滚动 | `native/final-settings-dark-880.jpg`、`final-settings-light-880.jpg`，最终滚动条无棋盘纹，页内滚动不改变参数，底栏固定；1180 窗口及深浅布局矩阵也检查通过 |
| 外观布局 | `native/final-appearance-dark-880.jpg`、`final-appearance-dark-max.jpg`：网格、卡片边距、滚动条及标题/底栏对齐 |
| 测试布局与安全状态 | `native/final-input-loading-dark-880.jpg` 顺序排列，`final-input-loading-dark-max.jpg` 并排；点击加载后仍“无待应用更改”，灰度、拖动、输入、加载、17 角色目标回归测试保留 |
| 窗口控制 | 实机红关闭、黄最小化（IsIconic确认）、绿最大化/还原、Alt+Space菜单；还原后圆角恢复；最大化后的按钮仍锚定窗口右上角 |
| 真实窗口拖动 | `dragging/native-trace.stdout.log` 与 `native-evidence.json`：更新窗口在桌面操作后实际位置多次变化，大小一直 1180×850；原生成功请求与延时真实 geometry 分开记录，不将返回 True 当作已移动。顶部命中、失败回退、弹窗隔离、释放/失活与最大化回退有专门回归 |
| 审阅 | 下拉/控制器与 native helper 独立审阅，几何失败回退递归已以 red→green 回归修复；最终 z-order 审阅无 Important/Critical 问题；Git diff检查无空白错误 |

## 未验证与交付边界

高对比、系统策略关闭及 helper 失败通过注入策略/错误的测试覆盖，没有修改真实 Windows 设置来做切换验收。混合 DPI、跨屏、Snap、鼠标边缘调整大小、长时间 GPU/功耗表现及其它 Windows/远程桌面环境尚未实机验收。原生移动失败时的手动回退通过模拟平台失败测试覆盖，当前 Windows 原生路径成功，因此没有真实失败环境实机验收。本轮未生成或验收新 Windows 发行包；旧包诊断结果不能代替新包验收。

默认入口保留原已保存 blur0，不擅自改变用户偏好；现在该滑块及数值输入可用，调整后可保存。验收用独立 `.local/material-v4/native-qa-sidebar.json` 保存 blur10；数值验收另用 `.local/material-v4/native-numeric-sidebar.json` 保存浅色80%/模糊5，未覆盖默认外观文件。旧正在运行的预览不会加载更新源码，需退出旧实例后从 v4 入口重新启动。
