# Pointer 演示与推广素材

[项目首页](<../../README.md>) · [推广文案](<../launch-kit.md>) · [商业化边界](<../commercial-readiness.md>)

## 内容与用途

- [横屏封面](<cover.png>)：1920 × 1080。
- [竖屏封面](<cover-portrait.png>)：1080 × 1920。
- [点击动效 GIF](<click-motion.gif>)：768 × 432，3 秒循环。
- 当前真实界面隔离渲染：[外观](<app-appearance.png>)、[动效](<app-motion.png>)、[测试](<app-tests.png>)、[设置](<app-settings.png>)。
- [中英 SRT 字幕](<pointer-demo.zh-en.srt>)：与 50 秒影片对齐；影片已有中英标题，避免平台重复叠加同样字幕。
- 完整横屏／竖屏 MP4 与素材包在 [beta.6 发布页](https://github.com/ReactionForge/Pointer/releases/tag/v1.3.0-beta.6) 下载。生成输出保存在被忽略的 `dist/promo/`，不将大视频提交至 Git 历史。

![点击动效](<click-motion.gif>)

## 真实性说明

使用当前 MaterialWindow 隔离渲染，不使用旧 UI 或生成的概念图代替软件界面。放大光标调用正式绘图实现与 ClickMotion；不改变实际按下／松开时长。示例循环中的按下信号由脚本产生，不是用户鼠标录制。

后台由 Mock 替代；应用、恢复、启动项、保存、资源预热均有禁止调用断言。更新检查／下载／安装由隔离上下文阻断。画面明确注明「非系统录屏」，没有虚构成功应用、恢复或性能数值。背景几何是视频设计，不是 Windows 毛玻璃实时效果。

## 复现

使用项目原有 D 盘虚拟环境与固定版本依赖，无需 MoviePy、在线生成 API 或额外 Python 库。单独安装 FFmpeg 至 D 盘工具目录，或使用已有本地 FFmpeg；不要将它的 EXE 提交进仓库。

```powershell
.\.build-env\Scripts\python.exe -m scripts.render_promo --stills-only
.\.build-env\Scripts\python.exe -m scripts.render_promo --ffmpeg D:\Tools\ffmpeg\bin\ffmpeg.exe
```

可用 `--format landscape` 或 `--format portrait` 单独输出；`--output` 指定视频目录，`--media` 指定封面／截图目录。输出为 H.264、yuv420p、AAC、30 fps、50 秒，启用 MP4 faststart，适合浏览器与常见视频平台。

完整双格式运行写入 `manifest.json` 与 `manifest-both.json`；单格式写入自己的清单，静态运行写入 `stills-manifest.json`，不会给旧视频或无关 MP4 重标来源。清单记录本次新生成视频的哈希、源代码指纹、字体哈希及 Python／Pillow／PySide／FFmpeg 版本。跨系统字体与渲染环境可能影响画面或文件字节，不保证任意环境逐字节一致。

本次执行时将已有 FFmpeg／ffprobe 复制到 D 盘仓库私有工具目录 `.local/publication/toolchain/`；这些工具不随公开素材或源码交付。FFmpeg 的自身许可证仍适用于工具本体；仅调用其编码，不重新分发工具。

## 音乐、字体和授权

音轨在 [制作脚本](<../../scripts/render_promo.py>) 内用正弦波程序合成，无第三方录音或采样。使用本机 Microsoft YaHei 字体栅格化文字，未分发字体文件；跨机复现可用 `--font` 指向具备合法使用权的中文字体。

历史光标与图标的商业来源仍未确认。程序生成、重新绘图或公开下载均不能自动解决原素材授权问题。因此本素材包不授予独立商用／转售许可，不可宣传成「全素材版权已清算」。详见 [商业化检查](<../commercial-readiness.md>)。

## 分镜

| 时间 | 画面 | 目的 |
| --- | --- | --- |
| 0–6 s | 品牌、圆润箭头 | 建立 Pointer 记忆点 |
| 6–14 s | 深浅双色卡片、同步移动的箭头 | 说明背景自适应配色 |
| 14–24 s | 实际外观页、造型轮换 | 展示个性化与安全预览 |
| 24–32 s | 原绘图逻辑的箭头／手形点击反馈 | 展示按住与回正 |
| 32–42 s | 实际测试页、备份／暂停／恢复说明 | 解释完整系统角色与可逆性 |
| 42–50 s | 下载地址、平台、beta 与授权边界 | 行动入口，不夸大稳定性 |

上传建议：横屏用于 GitHub／Bilibili，竖屏用于短视频。以实际平台规范裁剪，保留底部真实性提示，不添加不存在的用户数量或商业认证徽章。
