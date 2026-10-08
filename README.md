<div align="center">

# Pointer
### 让每一次指向，都清晰一点。

Windows 自适应光标工具 · 黑白对比 · 圆润动效 · 可预览、可恢复

[![Windows 10 / 11 x64](https://img.shields.io/badge/Windows-10%20%2F%2011%20x64-222222)](https://github.com/ReactionForge/Pointer/releases/tag/v1.3.0-beta.6)
[![版本](https://img.shields.io/badge/version-1.3.0--beta.6-orange)](https://github.com/ReactionForge/Pointer/releases/tag/v1.3.0-beta.6)
[![Windows 检查](https://github.com/ReactionForge/Pointer/actions/workflows/release.yml/badge.svg)](https://github.com/ReactionForge/Pointer/actions/workflows/release.yml)

[**下载安装包**](https://github.com/ReactionForge/Pointer/releases/download/v1.3.0-beta.6/Pointer-v1.3.0-beta.6-setup-x64.exe) · [便携 ZIP](https://github.com/ReactionForge/Pointer/releases/download/v1.3.0-beta.6/Pointer-v1.3.0-beta.6-windows-x64.zip) · [English](<README.en.md>) · [使用指南](<docs/getting-started.md>)

![Pointer 产品封面](<docs/media/cover.png>)

</div>

## 一款光标工具，不只是换一张箭头

从浅色文档到深色编辑器，Pointer 根据光标附近的背景明暗切换黑白配色。你可以在同一个桌面应用里调造型、大小、主体与边框颜色，预览点击反馈，再明确应用到 Windows。

- **看得清楚**：默认浅底黑主体白边、深底白主体黑边；也可固定配色。默认无彩色光晕，不代表护眼或医疗效果。
- **一整套体验**：覆盖 17 种 Windows 系统光标角色，保留加载动画；自绘光标的软件不保证被替换。
- **点击有反馈**：默认箭头倾斜、小手跟随，松开回正。强度和按下／松开时间可精确输入，也可关闭动效。
- **先预览，再应用**：参数草稿不会立即改变系统。界面外观保存与系统光标应用分别管理。
- **随时退回原样**：保留最初光标备份，支持暂停、恢复原光标；升级保留用户配置和开机启动选择。
- **本地工作**：不需要账号或 Python；光标功能无需联网。更新检查和下载会访问 GitHub，可在设置中关闭自动检查。

## 看一眼新版界面

![beta.6 外观页](<docs/media/app-appearance.png>)

![beta.6 动效页](<docs/media/app-motion.png>)

上图为当前 MaterialWindow 的隔离界面渲染，非旧版设计稿；不作为 Windows 实时背景模糊验收证据。

**[观看 50 秒演示视频／下载横竖屏素材](https://github.com/ReactionForge/Pointer/releases/tag/v1.3.0-beta.6)** · [视频制作与复现](<docs/media/README.md>)

## 30 秒开始使用

1. 从上方下载 EXE 安装包，或完整解压 ZIP 后打开 `Pointer.exe`。支持 Windows 10/11 x64，常规安装无需管理员权限。
2. 调整造型、配色和大小，先看浅色／深色双预览。
3. 点击 **应用更改**，再进入 **光标测试** 检查当前 Windows 光标。
4. 需要退出效果时，在 **应用设置** 暂停或恢复 Windows 原光标。关闭窗口不等于停止后台效果。

> **当前推荐体验版为 v1.3.0-beta.6，仍是预发行。** 主分支同步该功能基线不代表升级成稳定版；原稳定版 v1.1.1 保留。beta.3 用户请手动下载安装 beta.6 一次，旧版更新检查不会随新发布自行修复。发布 EXE 尚未代码签名，Windows 可能提示未知发布者。请核验来源与 SHA-256，不要关闭系统安全功能。

[下载与校验](<docs/getting-started.md#下载与校验>) · [问题反馈](https://github.com/ReactionForge/Pointer/issues) · [版本变化](<CHANGELOG.md>) · [beta.6 验收边界](<docs/releases/1.3.0-beta.6.md>)

## 有哪些边界？

- Windows 系统光标与应用自绘光标不同；游戏、图片抓手或部分远程环境可能使用自己的资源。
- 真实侧栏背景模糊需要受支持的 Windows 11 合成环境。Windows 10、高对比、关闭透明效果或窗口失活会使用回退，不修改全局系统设置。
- 混合 DPI、跨屏、Snap、真实高对比切换及长时间 GPU／功耗尚需进一步实机验收。首次生成非内置资源可能需要等待。
- 配置和原光标备份保存在 `%LOCALAPPDATA%\Pointer\data`，应用部署于相邻 `app` 目录。ZIP 首次成功应用后部署到持久目录；它不是完全零写入的便携模式。

## 开发与复现

Windows x64 + Python 3.13。在 D 盘克隆本仓库后：

```powershell
python -m venv .build-env
.\.build-env\Scripts\python.exe -m pip install -r requirements/dev.txt
.\.build-env\Scripts\python.exe -m pip install --no-deps -e .
.\.build-env\Scripts\python.exe -m unittest discover -s tests
.\.build-env\Scripts\python.exe -m pointer --gui
.\.build-env\Scripts\python.exe -m scripts.build_release
```

打包需要 Inno Setup 6、现有 .NET Framework 编译器与 Windows WinRT 元数据；用户运行成品不需要编译器。构建及运行依赖已固定版本。发布必须通过源码测试、冻结包诊断、隔离安装升级卸载检查。源码运行 `--apply` 会修改当前用户光标，不应当作安全预览命令。

[贡献与构建指南](<CONTRIBUTING.md>) · [架构](<docs/architecture.md>) · [文档导航](<docs/README.md>) · [安全报告](<SECURITY.md>) · [数据与隐私](<PRIVACY.md>)

## 授权与商业化

**源码可查看，但目前没有授予通用开源／商业再分发许可。** 项目代码与历史素材的权利归属尚待维护者确认；不能把公开仓库等同于 MIT 授权。Qt／PySide 等第三方组件继续受各自许可证约束。

本次提供的是可发布的预览版仓库、介绍文档和推广素材，不是已经完成权利审核、签名与全部实机验收的商业认证产品。[商业化检查清单](<docs/commercial-readiness.md>)明确区分已交付内容和销售前条件。

## 帮助 Pointer 被更多人看到

如果它解决了你的问题，欢迎 Star、分享演示或提交具体的 Windows 兼容性反馈。请附版本与复现步骤，隐藏用户名、私人路径和原光标备份。不买量、不虚构数据，也不保证热度。

[可直接使用的推广文案](<docs/launch-kit.md>) · [支持与常见问题](<SUPPORT.md>)
