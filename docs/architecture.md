# 架构与目录约定

## 运行流程

`python -m pointer`、源码快捷命令和打包后的 `Pointer.exe` 都进入 `pointer.app.main()`。`app` 负责命令分发、安装、旧版迁移、操作报告和失败恢复。

启用流程：保存原设置 → 配置 Windows 光标 → 检查当前用户登录启动项（仅新增或路径改变时写入） → 启动后台切换器。重新启用或升级时只停止后台实例，保留已有启动项，避免重复触发启动保护提示。明确选择停止或恢复时才移除启动项。后台切换器读取光标附近的背景亮度，通过 `contrast_theme` 选择配色，再更新系统光标。它不联网，也不保存屏幕图片。

## 程序模块

| 模块 | 职责 |
| --- | --- |
| `src/pointer/app.py` | 安装、停止、恢复、诊断与控制入口；下载目录中的按钮转交安装版 |
| `src/pointer/configure_cursor.py` | 光标注册表配置、原始备份校验、Windows 重新加载与恢复 |
| `src/pointer/adaptive_switcher.py` | 亮度采样、配色切换、动画载入、单实例和登录启动 |
| `src/pointer/click_motion.py` | 左键边沿、长按和 150 毫秒回弹的纯时间状态机 |
| `src/pointer/contrast_theme.py` | 17 个系统角色、资源名称和切换阈值 |
| `src/pointer/runtime_paths.py` | 源码、安装资源和持久数据路径的统一定义 |
| `src/pointer/__main__.py` | Python 模块命令入口 |
| `packaging/windows/entrypoint.py` | PyInstaller 和源码快捷命令的启动入口 |

运行模块仅依赖 Python 标准库；生成和视觉验证工具的 Pillow 依赖放在 `requirements/art.txt`，不进入应用运行包。

## 资源与开发工具

- `assets/cursors/adaptive/light`、`dark`：两套正式配色，共 34 个资源。
- `assets/cursors/reference`：原始固定黑色造型，17 个资源。
- `assets/cursors/legacy-invert`：历史原生反色实验，仅保留在源码中；正式安装包不包含它。
- `tools/generate`：CUR/ANI 和公开预览的生成代码。
- `tools/verify`：Windows 原生绘制、热点和动画检查，避免只检查文件是否存在。
- `web/cursor-test`：自包含测试网页。它使用系统光标，并由用户观察外观后记录结果。
- `docs/images`：README 引用的公开图片；其他实验截图归入 `.local/archive`。

## 文件和数据边界

| 场景 | 资源根目录 | 原配置、启动备份和状态 |
| --- | --- | --- |
| 源码运行 | 仓库根目录下的 `assets/` 和 `web/` | 仓库 `.local/data/` |
| 安装版运行 | 安装目录下的 `assets/` 和 `web/` | 安装目录相邻的 `data/` |
| 本地开发 | 工具生成公开资源或预览 | `.local/reports/`、`.local/archive/` |

安装版保持资源目录与备份目录分离，升级不会覆盖原始备份。Windows 商店宿主可能重定向 AppData；程序使用解析后的安装路径及相邻数据目录，保证登录启动时仍读取同一份备份。

DEV 点击动效只替换 Arrow 和 Hand。后台约每 8 毫秒读取左键当前按下状态，背景采样仍约每 50 毫秒一次。4 档缩小帧预加载到缓存，点击期间不读文件、不改启动项；配色切换后立即重新应用当前按压帧。所有帧围绕原热点缩放，加载 ANI 不参与按压动画。

源代码、正式资源、测试和说明进入 Git；`.local`、虚拟环境、`build`、`dist`、缓存和个人备份由 `.gitignore` 排除。重组目录和发布使用普通提交，保留 Git 历史。

## 发布规则

`VERSION` 是版本号来源，`pyproject.toml` 和构建脚本从它读取版本。发布标签必须与它相符。构建脚本仅收集正式资源、网页、Windows 入口和运行库，并生成文件清单、ZIP 和 SHA-256 校验文件。CI 通过单元测试和打包程序诊断后才发布。
