# Pointer

Windows 黑白自适应光标：浅色背景显示**黑色主体、白色边框**，深色背景显示**白色主体、黑色边框**。保留圆角造型和加载动画，无蓝光。

![深浅背景下的光标](dual-contrast-preview.png)

## 一键配置

1. 在 [Releases](https://github.com/ReactionForge/Pointer/releases/latest) 下载 `Pointer-v1.0.0-windows-x64.zip`。
2. 完整解压，打开其中的 `Pointer` 文件夹。
3. 双击 `一键安装.cmd`（也可使用 `install.cmd`），等待安装完成提示。

适用于 Windows 10/11 x64。发布包包含运行环境，安装和使用不需要 Python、管理员权限或联网。程序安装到 `%LOCALAPPDATA%\Pointer\app`，自动启用光标并随当前用户登录启动。安装成功后可以删除下载的压缩包和解压文件夹。

发布包尚未进行代码签名。Windows 可能显示来源或信誉提示；请核对本仓库的发布来源及随包提供的 SHA-256 校验值。项目不会要求关闭安全软件。

## 启用、停止与恢复

安装后，在开始菜单的 **Pointer** 文件夹中使用以下入口：

| 入口 | 行为 |
| --- | --- |
| 启用自适应光标 | 启动背景亮度检测，并启用登录自动启动 |
| 停止自动切换 | 关闭后台程序和登录启动，保留黑色主体、白色边框的固定配色 |
| 恢复原光标 | 关闭后台程序和登录启动，恢复安装前保存的 Windows 光标设置 |
| 打开测试页 | 离线测试深浅背景、文字选择、链接小手、加载和调整大小等状态 |

原始设置备份保存在 `%LOCALAPPDATA%\Pointer\data`，更新程序不会覆盖已有备份。升级时下载新版本、完整解压后再次运行 `一键安装.cmd`。若要移除程序，先使用“恢复原光标”，再删除 `%LOCALAPPDATA%\Pointer\app` 和开始菜单中的 Pointer 文件夹；数据目录可保留以备恢复。

## 效果与范围

- 覆盖 17 种 Windows 系统光标，包括箭头、文字选择、小手、加载、后台加载、帮助、精确选择、手写、禁止、四方向调整大小、移动、备用选择、位置选择、人物选择。
- 后台程序在本机检测光标附近的背景亮度，整只光标成对切换配色；中灰区间保留当前配色，减少来回切换。程序不上传屏幕内容。
- Windows“照片”的拖动手掌，以及部分应用、游戏和浏览器自行绘制的抓手或缩放光标，可能不采用 Windows 系统光标方案。
- 图形依据参考截图重绘，并非截图中主题的原始资源。

## 从源码运行

在 Windows 上安装 Python 3.13 后，从仓库目录运行：

```powershell
python pointer_app.py --apply
python pointer_app.py --test-page
python pointer_app.py --stop
python pointer_app.py --restore
```

`--apply` 会修改当前用户的光标设置。源码模式会从当前仓库读取资源，因此启用期间应保留仓库位置。日常使用建议安装 Release 发布包。

诊断只检查资源和发布包完整性，不应用光标设置：

```powershell
python pointer_app.py --diagnose --quiet --report diagnostics.json
```

发布包的 `Pointer.exe` 提供相同参数，并另有 `--install` 安装入口。自动化调用可读取 `--report` 指定的 JSON，`exit_code` 为 `0` 表示成功。

## 构建发布包

使用 Windows x64 和 Python 3.13：

```powershell
python -m venv .build-env
.\.build-env\Scripts\python.exe -m pip install -r requirements-build.txt
.\.build-env\Scripts\python.exe -m unittest discover -s tests
.\.build-env\Scripts\python.exe build_release.py
```

版本号取自 `VERSION`。构建输出为 `dist/Pointer-v<版本>-windows-x64.zip` 及对应 `.zip.sha256` 文件。打包采用目录形式，必须保留 `Pointer.exe` 旁的运行库和资源。构建脚本只收集程序及公开资源，不包含个人备份、运行状态或诊断报告。

光标资源已随源码提供，普通构建无需重新生成。修改造型时可另外安装 Pillow，再运行对应的 `create_*.py` 资源生成脚本。

[GitHub Actions](https://github.com/ReactionForge/Pointer/actions/workflows/release.yml) 支持手动构建；推送与 `VERSION` 一致的 `v<版本>` 标签会在测试和诊断通过后创建 GitHub Release，附上 ZIP 和 SHA-256 文件。
