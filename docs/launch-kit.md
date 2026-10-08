# Pointer 发布传播素材包 / Launch kit

## 使用前提与真实边界

本包服务于 1.3.0-beta.6 预发行介绍，不代表稳定版商业上线。先确认 [商业化就绪评估](<commercial-readiness.md>) 中的权利、签名及 QA 阻塞；维护者尚不能确认全部素材权利。完成视频制作、合并分支或获得视觉批准，都不等于可商业推广的清权证明。

功能依据 [项目说明](<../README.md>)、[beta.6 验收记录](<releases/1.3.0-beta.6.md>)、[资源说明](<../assets/README.md>) 与 [随包说明](<../packaging/windows/README.txt>)。发布时重新核对目标产物，不沿用旧版截图或历史测试数字冒充当前验收。

允许介绍：Windows 10/11 x64、17 种系统光标角色、默认黑白背景适配、加载动画、可调左键动效、草稿预览后显式应用、独立的界面外观保存。真正 host backdrop 仅用于受支持的 Windows 11 环境，其他情形回退。

不可宣称：已清权可商用、已完成全部实机验收、已签名、全平台通用、零延迟/零功耗、所有软件光标均可替换，或视觉素材得到 Apple/Microsoft 背书。禁止编造用户数量、评分、客户评价、销量、权威推荐或“必上热门”。宣传与分发效果不保证流量、转化或收入。

## 可直接使用的中文文案

**短标题**

> Pointer：黑白背景适配的 Windows 圆角光标

**一句话**

> 17 种系统光标角色，保留加载动画，可调点击动效；先预览草稿，再明确应用。

**简介**

> Pointer 是面向 Windows 10/11 x64 的圆角光标桌面应用。默认浅底黑主体白边，深底白主体黑边。可调整外观与左键动效，在内置页面观察黑白背景、输入、拖动和加载等状态。1.3.0-beta.6 为预发行版本，提供安装包与便携包；当前未代码签名，仍有实机验收和资产权利核验待完成。

**下载行动语**

> 阅读限制与校验说明，再从 GitHub 获取 beta.6；欢迎提交脱敏、可复现的反馈。

## English copy

**Headline**

> Pointer — rounded Windows cursors for light and dark backgrounds

**One-line description**

> 17 system cursor roles, loading animation and adjustable click motion. Preview a draft before explicitly applying it.

**Description**

> Pointer is a rounded cursor desktop app for Windows 10/11 x64. Its default black-and-white appearance adapts to light and dark backgrounds. Adjust cursor appearance and left-click motion, then explore input, dragging and loading in the built-in test page. Version 1.3.0-beta.6 is a prerelease with installer and portable packages. Current packages are unsigned; physical-device QA and asset-rights verification are still outstanding.

**Call to action**

> Read the limitations and checksum guidance before downloading the beta from GitHub. Reproducible, redacted feedback is welcome.

## 视频呈现规范：真实组件，隔离渲染

视频应使用 [真实 MaterialWindow 实现](<../src/pointer/ui/material_workspace.py>) 和 [项目光标艺术实现](<../src/pointer/cursor/art/>)，不是生成式 UI 提案，不重新绘制虚构控件。隔离思路可参考 [Material 捕获入口](<../scripts/capture_material_ui.py>) 与 [安全预览隔离](<../scripts/safe_preview.py>)：Mock 后端、不应用系统光标、不更改启动项，不检查、下载或安装更新。

**片内常驻或明显标注：** `隔离界面与光标渲染演示 · 非系统录屏` / `Isolated UI and cursor render demo · not a system capture`。

- 将真实 Qt 窗口内部画面与项目艺术帧合成到演示场景；不采集个人桌面、消息、其他窗口或真实系统光标操作。
- 渲染按下、保持、松开和加载状态可以说明艺术实现，但不等于物理输入、系统切换或真实时序验收。放大光标需标“放大预览”。
- 不在 Mock 后端显示或剪出“真实系统应用成功”的假证据。可以展示应用按钮及其草稿语义，但只用字幕解释正常产品的显式应用行为。
- 界面内部透明层渲染不是 Windows 桌面合成；如展示模糊参数，注明它是界面演示，不能宣称视频证明真实 host backdrop。
- 不使用 [历史生成提案](<design/cursor-family-prompts.json>) 替代成品窗口。图标、实际光标艺术与字体的推广使用仍需先核验权利。
- 默认字幕版可无音乐、无旁白。音频、配音、字体文件或外部片段只有在来源和视频使用许可确认后才加入。

### 输出位置与交付记录

`docs/media/` 用于经过检查、适合随仓库公开的封面和短预览；`dist/promo/` 用于生产视频、字幕及制作清单。后者属于 [忽略的构建产物范围](<../.gitignore>)，不会因为合并源码自动出现在仓库或 GitHub Release。

本次实际制作项：

| 交付 | 内容与入口 |
| --- | --- |
| 横／竖屏视频 | 50 秒、30 fps、H.264／AAC；1920×1080 与 1080×1920，见 [发布页](<https://github.com/ReactionForge/Pointer/releases/tag/v1.3.0-beta.6>)。 |
| 封面与预览 | [横屏封面](<media/cover.png>)、[竖屏封面](<media/cover-portrait.png>)、[点击 GIF](<media/click-motion.gif>)。 |
| 字幕与说明 | [中英字幕](<media/pointer-demo.zh-en.srt>)、[素材说明](<media/README.md>)。 |
| 制作入口 | [自动制作脚本](<../scripts/render_promo.py>)；音轨为程序合成、无第三方采样，使用本机字体栅格化且不分发字体文件。 |

实际编码结果、解码检查与哈希见 [交付验收记录](<releases/main-publication.md>)。视频成品与制作清单由脚本输出至被忽略的生产目录；封面与短预览随源码追踪。未把渲染检查写成真实系统应用验收。

## Bilibili 50 秒短视频脚本

标题建议：**Windows 光标也能有圆角和按下动效？Pointer beta.6 演示**

片内持续保留隔离渲染标注；以下每段按时间点切换，总长 50 秒。字幕可直接作为无旁白版本；旁白为可选录制文本，不是既有录音。

| 时间 | 画面与动作 | 中文字幕 / 可选旁白 |
| --- | --- | --- |
| 00–06 s | 品牌与真实圆润箭头艺术，注明放大渲染。 | “让每一次指向，都清晰一点。” |
| 06–14 s | 深浅双背景与同步移动的黑白箭头。 | “浅色、深色，都看得清。” |
| 14–24 s | 当前外观页隔离渲染、真实造型轮换；不伪造参数提交。 | “你的桌面，你的光标。先预览造型、配色和大小。” |
| 24–32 s | 正式 ClickMotion 和绘图逻辑的箭头／手形按住、松开循环。 | “点击，也有轻巧的回应。按住保持，松开回正。” |
| 32–42 s | 当前测试页；文字解释 17 种系统角色、备份、暂停与恢复，不实际执行。 | “先预览，再应用。随时回到原样。” |
| 42–50 s | 下载地址、平台、beta、未签名与素材权利限制。 | “从一个小细节，重新喜欢你的桌面。” |

英文字幕可使用上述 English copy 的对应事实；不得省去 prerelease、unsigned 和 render-demo 边界。默认回正约 150 ms 是项目默认值；视频剪辑的节奏不证明实际响应延迟。

**Bilibili 简介模板**

> Pointer 1.3.0-beta.6：Windows 10/11 x64 圆角光标、17 种角色、背景适配和可调点击动效。
>
> 本视频由真实 MaterialWindow 和项目光标艺术隔离渲染合成，非系统录屏；未更改演示机器的系统光标或开机启动。当前为未签名预发行，仍有实机 QA 和素材权利待核验，不代表商业清权完成。
>
> 仓库与下载：[ReactionForge/Pointer](<https://github.com/ReactionForge/Pointer>) · [beta.6 发布页](<https://github.com/ReactionForge/Pointer/releases/tag/v1.3.0-beta.6>)。请阅读限制并校验下载；欢迎提交脱敏的复现步骤。

建议标签：`Windows`、`桌面美化`、`鼠标光标`、`软件演示`。不以此预测平台推荐或播放量。

## 社交发布模板

### 中文短帖

> Pointer beta.6：Windows 10/11 x64 圆角光标，17 种系统角色，黑白背景适配和可调点击动效。演示为真实界面与项目艺术的隔离渲染，非系统录屏。预发行未签名，实机 QA 和权利核验尚未完成。先读限制，再试用并反馈：[仓库](<https://github.com/ReactionForge/Pointer>)。

### English short post

> Pointer beta.6 brings rounded light/dark Windows cursors, 17 system roles and adjustable click motion. Video: isolated real-UI/project-art render, not system capture. Unsigned prerelease; device QA and asset-rights checks remain open. Read the limits before trying it: [GitHub](<https://github.com/ReactionForge/Pointer>).

### 图文发布结构

1. 实际渲染封面与版本；注明隔离演示，不用生成提案冒充成品。
2. 两项可核验功能：双背景轮廓、左键动效调节。
3. 预发行、未签名、实机与权利限制。
4. 仓库/发布页与具体反馈问题，例如“在哪个应用中出现自绘光标差异？”不编造回答或好评。

## 发布前最后核对

- [ ] 完成 [商业化就绪评估](<commercial-readiness.md>) 对应推广渠道的权利核验；未解决时只作内部审阅，不宣称可商用。
- [ ] 对照 [beta.6 验收记录](<releases/1.3.0-beta.6.md>)，所有功能与限制仍与最终产物一致。
- [ ] 隔离说明在视频、封面/简介及社交帖中清晰，不用渲染证据替代系统验收。
- [ ] 去除私人路径、日志、通知、用户名和未经许可的字体/音频/外部图像。
- [ ] 实测视频时长与字幕；核实下载链接和哈希，明确未签名状态。
- [ ] 无假评价、无假指标、无背书暗示、无流量或性能保证。
