# 参与贡献 / Contributing

欢迎可复现的问题报告、小范围修复、测试与文档贡献。先阅读 [项目说明](<README.md>)、[开发约束](<AGENTS.md>)、[架构说明](<docs/architecture.md>) 及 [beta.6 验收记录](<docs/releases/1.3.0-beta.6.md>)。安全问题请走 [安全报告说明](<SECURITY.md>)，不要公开提交可利用细节。

## 提交前沟通

- 一般问题通过 [GitHub Issues](<https://github.com/ReactionForge/Pointer/issues>) 提交，写明版本、Windows 版本、复现步骤、预期及实际结果；日志和截图先脱敏。
- 大功能、UI 方向、依赖或打包策略调整先开 issue 商议。PR 通常面向 DEV；维护者另行明确批准的发布合并除外，不自行创建发行标签或推送 main。
- 不把私人机器数据、原始系统备份、缓存、日志或本地候选包提交到仓库；遵循 [忽略规则](<.gitignore>)。

## 开发环境与检查

当前开发目标为 Windows x64 / Python 3.13。固定依赖见 [开发依赖](<requirements/dev.txt>)、[构建依赖](<requirements/build.txt>) 和 [运行依赖](<requirements/runtime.txt>)，项目安装入口见 [项目元数据](<pyproject.toml>)。

```powershell
python -m venv .build-env
.\.build-env\Scripts\python.exe -m pip install -r requirements/dev.txt
.\.build-env\Scripts\python.exe -m pip install --no-deps -e .
.\.build-env\Scripts\python.exe -m unittest discover -s tests
.\.build-env\Scripts\python.exe -m pointer --diagnose --quiet
```

源码诊断不能代替冻结程序诊断。声称 Windows 构建可用前，运行全套测试和最终包的 `--diagnose`，并报告版本、提交、结果及跳过原因；包验收方式见 [发布流程](<.github/workflows/release.yml>)。`POINTER_PACKAGE_ROOT` 用于显式启用隔离打包集成检查，不应指向用户正在使用的安装目录。

## 安全边界

- 单元测试禁止真实系统设置写入。预览应使用 Mock/隔离后端；[Material 捕获入口](<scripts/capture_material_ui.py>) 与 [安全预览隔离](<scripts/safe_preview.py>) 可供参考。
- 普通 `--apply` 会改变当前用户的系统光标。不要为了截图或验证未经允许修改系统光标、注册表、开机启动或全局透明/高对比设置。
- 保留最初光标备份。重应用与升级不得删除并重建未变化的启动项；失败应保留草稿和可恢复状态。
- 光标预览与 CUR/ANI 使用 [统一艺术实现](<src/pointer/cursor/art/>)；正式资源约定见 [资源说明](<assets/README.md>)。不要随意重录像素/热点基线来掩盖回归。

## PR 内容

说明解决的问题、改动边界、验证命令与真实结果。UI 改动附深浅主题和窄窗证据，并注明是离屏渲染还是系统桌面捕获。列出未测项，不把截图、模拟输入或旧包诊断写成新包实机验收。

新增依赖与素材注明来源、许可、版本、参考输入及分发条件，不提交未经授权的截图、字体或音频。维护者尚不能确认全部现有资产权利；参见 [商业化就绪评估](<docs/commercial-readiness.md>)。本贡献说明不授予项目 MIT 许可，不自动完成权利转让；贡献者只提交自己有权提供的内容，并与维护者确认拟采用的许可范围。

**English:** Keep changes scoped, target DEV unless the maintainer explicitly requests a release merge, preserve original cursor backups, and test without changing a user's system. Report skipped and untested cases honestly. Do not submit private machine data or assets with unverified redistribution rights.
