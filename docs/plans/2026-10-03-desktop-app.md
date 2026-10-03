# Pointer Desktop App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 交付精致的 Windows 光标配置 APP，将测试网页移植为原生测试页，重构为清晰目录，并提供 GitHub 安装包下载。

**Architecture:** 保留现有光标引擎能力，依次收敛为 cursor、windows、application 和 ui。GUI 维护草稿，通过 application 应用配置；预览与真实资源共用绘图实现，测试页显示 Windows 原生共享光标。安装、升级和卸载复用 application 的备份及回滚机制。

**Tech Stack:** Python 3.13、PySide6-Essentials 6.11.2、Pillow 12.3.0、PyInstaller 6.22.3、Inno Setup、unittest、GitHub Actions。

**Spec:** [desktop-app.md](../design/desktop-app.md)。用户已确认精致界面和功能范围，追加内置测试及清晰架构要求；本计划包含这些要求。

## Global Constraints

- Windows x64；无需管理员权限；用户无需安装 Python 或 Qt。
- 所有开发提交推送 DEV；不合并 main；桌面首版作为 GitHub 预览版提供下载。
- 只使用 QtCore、QtGui、QtWidgets，不依赖 WebEngine 或本地 HTTP 服务。
- 关闭设置窗口会退出 GUI 进程，后台服务继续工作；后台延迟加载 GUI 模块。
- 大小为 24、32、40、48、64；动效强度 0–100%；按下 40–200 ms，松开 80–400 ms。
- 默认 32、强度 50%、按下 60 ms、松开 150 ms；默认自动黑白适配；升级保留旧动效选择。
- 浅背景黑主体白边框，深背景白主体黑边框；箭头整体倾斜、顶部向左下且下方轻微跟随。
- 预览不改变系统；只有应用配置改变光标；开机启动开关独立，不重写未改变的 Run 值。
- 最初 Windows 光标备份不可覆盖；失败不能错误报告成功；配置导入校验后只更新草稿。
- 压缩安装包目标约 50 MiB 以下，报告实际体积及资源占用。
- Qt/Python/Pillow/PyInstaller 随包提供相应许可，保留可替换动态 Qt 库和源码获取说明。

## Review Focus

1. 损坏、未知版本和超大 JSON 配置必须在任何系统写入前失败，并保留旧数据（Task 2）。
2. Windows 商店宿主虚拟化 AppData、路径含空格/中文及跨旧版本安装位置必须找到原备份（Task 1、6）。
3. 大角度、高 DPI、最大尺寸、快捷连点和失焦不能裁切或卡住动效（Task 3、5）。
4. 升级时 GUI/后台占用文件或恢复失败必须可恢复，不删除原备份或误报安装/卸载成功（Task 4、6）。
5. Qt 私有光标及原生子窗口不能掩盖 Windows 系统共享光标，离开加载测试恢复正常（Task 5）。

## Interface map

```python
# cursor/settings.py
@dataclass(frozen=True)
class CursorSettings:
    schema_version: int = 1
    appearance: str = "adaptive"
    light_body: str = "#000000"
    light_outline: str = "#ffffff"
    dark_body: str = "#ffffff"
    dark_outline: str = "#000000"
    size: int = 32
    motion: str = "tilt"
    strength: int = 50
    press_ms: int = 60
    release_ms: int = 150
    startup: bool = False

# These are the required public signatures, implemented in their owning tasks.
# SettingsStore(root: Path): load(legacy_mode_path: Path, startup_enabled: bool),
# save(settings: CursorSettings), import_file(path: Path), export_file(path, settings).
# CursorSettings.from_dict(value: dict) -> CursorSettings; to_dict() -> dict.
# RenderRequest(settings, role: str, theme: str, frame: int, dpi: int).
# render_cursor(request) -> tuple[PIL.Image.Image, tuple[int, int]].
# encode_cur(images_and_hotspots) -> bytes; encode_ani(frames, interval_ms) -> bytes.
# ResourceBundle: key, root, size; paths(theme, frame=0) -> dict[str, Path].
# prepare_resources(settings: CursorSettings, cache_root: Path) -> ResourceBundle.
# WindowsBackend: snapshot(), stop(), apply(bundle, appearance), start(),
# restore(snapshot), startup_enabled(), set_startup(enabled), restore_original().
# Application(data_root, install_root, backend=None): settings(), snapshot(),
# apply(settings), pause(), resume(), restore(), set_startup(enabled), prepare_upgrade().
# MainWindow(application: Application): draft(), set_draft(settings), request_apply().
# TestPage(application: Application): scenario(name), click_state(), finish_busy().
```

`Application` 操作返回字典，稳定字段为 `running`、`startup_enabled`、`settings`、`last_error`；失败抛出异常给 CLI/GUI 统一转换为反馈。预览页不调用 application.apply。`frame` 为 0–4，0 是正常形态；所有资源帧保持一致热点。`dpi` 为 96/144/192/288/384/768，生成资源包含对应尺寸。

### Task 1: 重构现有代码并保留所有能力

**Files:** 创建 `src/pointer/cursor/`、`src/pointer/cursor/art/`、`src/pointer/windows/`、`scripts/` 和 `tests/unit/`。移动 `runtime_paths.py`→`paths.py`、`app.py`→`cli.py`、`click_motion.py`→`cursor/motion.py`、`configure_cursor.py`→`windows/scheme.py`、`adaptive_switcher.py`→`windows/engine.py`。将 Win32 声明拆到 `windows/api.py`、启动项操作拆到 `windows/startup.py`、安装文件操作拆到 `windows/installation.py`。旧生成器归入 art 的 arrow、hand、roles、palette、animation、codec 六个模块。更新 `pyproject.toml`、`packaging/windows/entrypoint.py`、现有测试、工作流、README 和架构文档。

**Interfaces:** 产出新的导入路径；CLI 显式参数与旧输出保持兼容。此阶段不改变几何、配色、原始备份或运行启动项。原有测试移动后仍完整 discover，全部测试目录含 `__init__.py`。

- [ ] 先记录 `python -m unittest discover -s tests` 的 23 项基线、CUR/ANI 文件 SHA、Run 值及最后写入时间、原备份 SHA；记录在忽略的 `.local/reports/`。
- [ ] 添加目录/迁移回归测试，运行确认旧结构不能通过。

```python
def test_runtime_paths_prefer_installed_sibling_data(self):
    from pointer.paths import resolve_paths
    root = Path("C:/Users/test/AppData/Local/Packages/Host/LocalCache/Local/Pointer/app")
    paths = resolve_paths(root, Path("C:/Users/test/AppData/Local"), frozen=True)
    self.assertEqual(paths.data_root, root.parent / "data")
```

- [ ] 实现 `resolve_paths(root, local_app_data, frozen) -> RuntimePaths`，安装目录特征与受验证包清单联合判定；源码数据仍使用 `.local/data`。保留通过旧系统方案解析旧资源目录的迁移逻辑，不执行从注册表读取的任意命令。
- [ ] 用文件移动和导入调整完成重构；原脚本收敛为 `scripts/generate_cursors.py`、`scripts/build_release.py`、`scripts/serve_test.py`，工具不保留第二套绘制实现。
- [ ] 跑全部旧测试、源码 `--diagnose`、默认资源 SHA 比较。命令入口使用 `python -m pointer --diagnose`；包清单校验和旧模式升级测试继续通过。
- [ ] 提交 `refactor: organize cursor core windows backend and development tools`。

### Task 2: 版本化设置与安全迁移

**Files:** 创建 `src/pointer/cursor/settings.py`、`tests/unit/cursor/test_settings.py`；更新 `paths.py`、`cli.py`、`requirements/runtime.txt`、`requirements/dev.txt`、`requirements/build.txt`。依赖分组：runtime 固定 Pillow 和 PySide6-Essentials；build 引用 runtime 并固定 PyInstaller；dev 引用 build。

**Interfaces:** 实现 Interface map 的 CursorSettings 和 SettingsStore。只接受 schema_version=1；颜色归一化为六位十六进制；数值必须是整数而非布尔值；appearance 为 adaptive/light/dark，motion 为 tilt/shrink/off。JSON 大小上限 64 KiB，未知字段或未知格式版本拒绝。缺少新设置时迁移旧动效及实际启动状态；已存在但损坏的文件保留并报告错误，不能静默覆盖。

- [ ] 创建以下真实文件存储测试，观察导入/接口失败，再实现校验和原子存储。

```python
def test_invalid_import_leaves_previous_file_untouched(self):
    store = SettingsStore(Path(self.folder.name))
    original = CursorSettings(motion="shrink")
    store.save(original)
    before = store.path.read_bytes()
    invalid = store.path.parent / "import.json"
    invalid.write_text('{"schema_version":1,"size":999}', encoding="utf-8")
    with self.assertRaises(ValueError):
        store.import_file(invalid)
    self.assertEqual(store.path.read_bytes(), before)

def test_migration_preserves_existing_startup_and_mode(self):
    legacy = Path(self.folder.name) / "click-motion-settings.json"
    legacy.write_text('{"mode":"shrink"}', encoding="utf-8")
    loaded = SettingsStore(legacy.parent).load(legacy, startup_enabled=True)
    self.assertEqual((loaded.motion, loaded.startup), ("shrink", True))
```

- [ ] 补充缺失文件、损坏 JSON、未知版本、64 KiB 上限、大小枚举、时间/强度边界、错误颜色及 bool 伪整数测试。导出仅 schema 与用户属性，不包含任何路径、备份、进程或注册表数据。
- [ ] `save` 使用同目录临时文件和 os.replace；失败保留原文件。导入返回校验后的 CursorSettings，不调用 save 或 Windows API。
- [ ] 运行 `python -m unittest tests.unit.cursor.test_settings` 后跑全部回归；提交 `feat(settings): add validated persistent cursor preferences`。

### Task 3: 可配置绘图、DPI 与缓存

**Files:** 更新 `cursor/art/`、`cursor/motion.py`，创建 `cursor/resources.py`、`tests/unit/cursor/test_resources.py`、`tests/unit/cursor/test_motion.py`；更新默认资源生成脚本。

**Interfaces:** 实现 RenderRequest、render_cursor、encode_cur、encode_ani、ResourceBundle 和 prepare_resources。正常/点击帧共享透明边距及热点。配置强度对应箭头角度 `-12*strength/100`、小手 `-24*strength/100`、缩放 `1-.2*strength/100`；默认强度保留现有倾斜中心及最大帧效果。motion=off 返回 frame0，强度0也无形变。ClickMotion 改为接收 press_ms/release_ms，输出归一化帧0–4，保留快速重按与松开连续性。

- [ ] 先写最大参数资源与缓存失败测试。

```python
def test_extreme_settings_have_safe_bounds_and_fixed_hotspots(self):
    for size in (24, 32, 40, 48, 64):
        for role in ("arrow", "hand"):
            settings = CursorSettings(size=size, strength=100)
            images = [render_cursor(RenderRequest(settings, role, "dark", f, 192))
                      for f in range(5)]
            self.assertEqual(len({hotspot for _, hotspot in images}), 1)
            for image, _ in images:
                x0, y0, x1, y1 = image.getchannel("A").getbbox()
                self.assertGreater(x0, 0)
                self.assertGreater(y0, 0)
                self.assertLess(x1, image.width)
                self.assertLess(y1, image.height)
```

- [ ] 旋转绕既定中心，所有轮廓点距离保持；先计算最大帧包围盒，再为整个帧组统一分配透明边距和热点偏移；不要对每帧独立居中。大小表示可见光标逻辑尺寸，缓存加载请求包含画布尺寸，避免 Windows 自动缩小边距导致实际尺寸失准。
- [ ] 配色映射保持抗锯齿和 alpha，应用全部17角色。加载角色继续编码真实24帧 ANI，DPI 和 size 使用同一尺寸映射。两套主体/边框任意颜色由同一 palette 函数处理。
- [ ] 缓存键为归一化设置、绘图格式版本的 SHA-256；临时目录完整生成并校验后原子发布。异常留下旧缓存可用；只删除包含有效自有清单的废弃缓存。
- [ ] 添加轻/深两套配色、全部大小/DPI、ANI帧差异、强度0、motion=off、快速重按、短点按、按住、松开持续时间、同配置缓存复用及失败缓存不替换旧缓存测试。
- [ ] 跑全部测试和 Windows LoadImage/GetIconInfo 资源诊断，提交 `feat(cursor): generate configurable cached cursor resources`。

### Task 4: 应用事务、启动项及命令入口

**Files:** 创建 `src/pointer/application.py`、`tests/unit/windows/test_application.py`；更新 windows 的 engine、scheme、startup、installation，更新 cli、__main__ 和打包入口。

**Interfaces:** 实现 WindowsBackend 和 Application。backend 注入便于真实存储配合失败模拟。snapshot 包含系统方案和运行/启动状态；Application.apply 校验、准备资源、停止旧实例、保存并加载、启动和就绪验证；异常恢复文件和原 backend snapshot。set_startup 比较实际值，只改变不同值；pause 只暂停引擎，不改变启动项；restore 恢复最初光标并停服务/取消启动，保留外观设置。

- [ ] 使用临时 SettingsStore 和 mock WindowsBackend 创建启动失败回滚测试；mock 仅替代 Windows 系统边界。

```python
def test_failed_helper_start_restores_saved_settings_and_run_choice(self):
    old = CursorSettings(motion="shrink", startup=True)
    app = Application(self.data_root, self.install_root, backend=self.backend)
    app.store.save(old)
    before = app.store.path.read_bytes()
    self.backend.start.side_effect = RuntimeError("not ready")
    with self.assertRaisesRegex(RuntimeError, "not ready"):
        app.apply(CursorSettings(motion="tilt", startup=True))
    self.assertEqual(app.store.path.read_bytes(), before)
    self.backend.restore.assert_called_once()
    self.backend.set_startup.assert_not_called()
```

- [ ] 实现完整事务。恢复失败的原因合并返回，GUI显示失败，不显示已应用。运行状态以互斥量/事件和就绪检查为准，不仅依赖遗留 JSON 中的 running=true。
- [ ] engine 启动读取应用配置，缓存全角色与动效；自动背景模式保持原稳定判定，fixed模式固定选择；off模式继续自动适配但不处理形变。循环不绘图、不写启动项。
- [ ] 分离 `resume` 与 `set_startup`。CLI 保留 --install/--apply/--stop/--restore/--tilt/--shrink/--diagnose/--run 的兼容行为；新增 --gui、--test-page、--prepare-upgrade、--uninstall、--data-dir、--install-dir。测试覆盖重启选择保持、启动项未变化不写、暂停不取消启动和原备份 SHA 不变。
- [ ] --run 分支在任何 GUI import 之前返回；无参数进入GUI。--test-page 打开原生测试页，原网页仅 scripts/serve_test.py 开发使用。
- [ ] 真实 Windows 在测试目录验证升级、应用和恢复，再恢复当前用户原状态；提交 `feat(app): add transactional configuration and independent startup controls`。

### Task 5: 精致 GUI 与原生测试页

**Files:** 创建 `src/pointer/ui/__init__.py`、main_window.py、theme.py、workers.py、preview.py、native_cursor.py；创建 `ui/pages/appearance.py`、motion.py、tests.py、preferences.py；创建 `tests/unit/ui/test_window.py`、test_native_cursor.py、test_test_page.py。更新 `cli.py`、`pyproject.toml` 与桌面图标。

**Interfaces:** 实现 MainWindow、TestPage。页签对象有明确 objectName；MainWindow 管理已应用和草稿两个 CursorSettings。workers 使用 QObject/QThread 的信号传递结果，工作线程不直接修改 Qt 控件。preview 调用 Task3 render_cursor 并转换为 QImage。测试页通过 NativeCursorFilter 拦截 WM_SETCURSOR，调用 LoadCursorW(NULL,系统角色ID) 和 SetCursor，使用共享句柄，不复制或销毁。

- [ ] 安装已批准方案的依赖并锁定 runtime 文件；使用 Qt Widgets、石墨侧栏/浅内容区、圆角卡片、清晰数值滑块、双色预览、运行状态和底部应用栏。先完成外观、动效、应用设置三页及以下离屏测试。

```python
def test_preview_changes_draft_without_applying_system_settings(self):
    window = MainWindow(self.application)
    slider = window.findChild(QSlider, "strengthSlider")
    slider.setValue(75)
    self.assertEqual(window.draft().strength, 75)
    self.application.apply.assert_not_called()
    self.assertTrue(window.findChild(QPushButton, "applyButton").isEnabled())
```

- [ ] 连接全部字段、颜色选择器、草稿重置、导入导出、运行/暂停、恢复和启动开关。异步操作禁用重复提交，完成/失败后恢复可操作状态。展示具体失败原因；关闭有草稿时询问放弃或返回，普通关闭退出GUI且不调用pause/restore。
- [ ] GUI单实例使用命名事件/本地通信激活原窗口，避免第二窗口同时应用。应用升级准备通过明确事件请求 GUI 退出，若有未应用草稿则提示用户并中止升级，不能强制丢弃。
- [ ] 以原网页结构移植所有场景：亮度滑块、黑白交界、灰度块、深浅箭头空白区和小手按钮、I形文字输入、拖动卡片、受限等待/后台忙碌区、禁用/移动/各缩放角色。测试用系统光标，预览用绘图，不混淆。
- [ ] 测试鼠标角色与加载恢复：为原生子控件/viewport建立 hwnd→role 映射；nativeEventFilter 只处理自有测试控件；其他控件保持 Qt 默认行为。计数记录左键，release、focusOut、hideEvent、capture loss 都清理按下状态。

```python
def test_focus_loss_clears_test_press_state(self):
    page = TestPage(self.application)
    surface = page.scenario("light-arrow")
    QTest.mousePress(surface, Qt.MouseButton.LeftButton)
    QApplication.sendEvent(surface, QFocusEvent(QEvent.Type.FocusOut))
    self.assertFalse(page.click_state()["down"])

def test_native_filter_uses_shared_windows_cursor(self):
    with patch("pointer.ui.native_cursor.load_system_cursor", return_value=1234) as load:
        with patch("pointer.ui.native_cursor.set_system_cursor") as set_cursor:
            filter = NativeCursorFilter()
            filter.show_role("hand")
            load.assert_called_once_with("hand")
            set_cursor.assert_called_once_with(1234)
```

- [ ] 运行 `QT_QPA_PLATFORM=offscreen` 的 GUI 测试和渲染截图，检查900×700与1100×760、高 DPI、中文和键盘路径；在真实 Windows 打开界面并提供测试区域供用户实际鼠标检查，不把离屏点击当作真实物理动效验证。
- [ ] 提交 `feat(ui): add polished desktop settings and native cursor tests`。

### Task 6: 安装、升级、卸载与便携包

**Files:** 创建 `packaging/windows/installer.iss`、图标和说明；更新 `scripts/build_release.py`、windows/installation.py、cli.py、开始菜单快捷方式及许可证打包；创建 `tests/unit/windows/test_installation.py`、`tests/integration/test_packages.py`。

**Interfaces:** `build_release(version, compiler: Path) -> dict` 生成ZIP、安装EXE及sha256。installer按用户目录安装，升级前调用受验证现有 EXE --prepare-upgrade；文件复制前必须成功退出GUI/引擎。uninstaller调用 --uninstall 恢复并停服务，失败中止删除。用户数据位于程序目录外，不进入程序文件清理清单。

- [ ] 在正式改安装流程前，添加有用户文件的旧包与被占用文件测试。

```python
def test_cleanup_preserves_modified_and_user_added_files(self):
    root = self.install_root
    (root / "user-note.txt").write_text("mine")
    owned = root / "old.dll"
    owned.write_bytes(b"modified")
    cleanup_owned_files(root, {"old.dll": sha256(b"original").hexdigest()}, {})
    self.assertEqual(owned.read_bytes(), b"modified")
    self.assertTrue((root / "user-note.txt").exists())
```

- [ ] Inno Setup 设置 PrivilegesRequired=lowest；固定 AppId，按用户注册卸载入口。只在安装选项明确勾选时创建桌面快捷方式；开始菜单提供“Pointer”和“卸载”。新安装不自动启用启动项，旧用户保持实际启动状态。
- [ ] 安装/升级检查包清单，停止旧进程，复制到临时部署区，切换目录失败时恢复上一版本，完成后按先前状态恢复服务。AppData 虚拟化旧路径迁移从已验证方案/清单确定，迁移前后备份 SHA 相同。
- [ ] ZIP无参数打开GUI，首次应用才部署用户目录中的持久文件；旧一键安装/恢复命令继续可用。安装EXE复用相同manifest和应用操作，避免两套配置逻辑。
- [ ] 源码构建排除QtWebEngine/QtNetwork以外不需要的模块，但保留QtWidgets真正依赖、Windows平台插件、中文渲染和颜色对话框；逐项诊断确认裁剪未破坏界面。收集第三方许可证及动态库替换说明。
- [ ] 安装包 smoke test 使用独立 --data-dir/--install-dir，不卸载当前实际使用的 Pointer。覆盖含空格/中文路径、升级退出超时、系统恢复失败、原备份缺失或损坏、清除用户配置选项和已有不同Run值保护。
- [ ] 执行干净安装→改变设置→升级→确认设置/启动项/备份→恢复→卸载；打包 --diagnose 必须检查Qt平台插件、所有CUR/ANI、许可证和清单。
- [ ] 提交 `feat(installer): package reversible desktop installation and upgrades`。

### Task 7: 整体验证与 GitHub 预览版交付

**Files:** 更新 `.github/workflows/release.yml`、`VERSION`、README.md、CHANGELOG.md、docs/architecture.md、docs/usage.txt、packaging/windows/README.txt；创建 `.local/reports/` 中的实际验证记录。

- [ ] 支持版本 `1.3.0-beta.1`，Windows数值版本为(1,3,0,0)，产品文本版本为完整预览版本；标签、VERSION、清单与发布文件一致。版本校验接受明确的beta后缀，拒绝路径符号/命令字符。

```python
def test_preview_version_keeps_numeric_windows_version(self):
    from scripts.build_release import parse_version
    self.assertEqual(parse_version("1.3.0-beta.1"), ((1, 3, 0, 0), "1.3.0-beta.1"))
    with self.assertRaises(ValueError):
        parse_version("1.3.0/../bad")
```

- [ ] 工作流安装固定依赖及官方 Inno Setup，运行全部 unittest、Qt离屏测试、构建EXE/ZIP、打包诊断、安装/卸载隔离检查、SHA核对。保存截图与安装日志为诊断artifact。
- [ ] 本地运行完整验证，记录实际安装包/ZIP体积、GUI与后台内存、关闭GUI后的后台CPU和进程模块；确认--run未加载Qt。检查未改变Run最后写入时间和原备份SHA。
- [ ] 整分支独立代码审查，修复有证据的问题，再执行受影响验证。没有新的变化或疑点时不重复全量测试。
- [ ] 将所有代码和文档推送DEV，云端完成后下载并验证实际artifact；对与本机包一致的设置/资源/安装入口进行诊断。
- [ ] 从已验证DEV提交创建 v1.3.0-beta.1 标签，GitHub Release标记 prerelease、latest=false，上传安装EXE、ZIP和各自SHA。此步骤落实用户明确请求的GitHub直接下载；保持main和当前stable不变。
- [ ] README提供下载按钮、界面图、首次应用和APP测试页使用说明；最终交付下载链接、界面截图、验证结果、实测大小和真实物理点击验证的适用限制。
- [ ] 提交 `release: prepare desktop preview downloads and documentation`，确认DEV工作区干净且远程提交一致。

## Self-review and handoff

规格每项均映射到Task：结构1；设置迁移2；绘制/大小/配色/动画3；事务/启动4；精致界面和网页移植5；安装升级卸载6；GitHub下载/实测7。五个Review Focus均有对应失败测试或隔离验证。没有占位步骤；Interface map 中的名称在任务间保持一致。

建议当前会话直接逐步实现，完成后独立审查：任务共享设置、资源与事务接口，按依赖顺序实现便于保护现有Windows配置。执行前须由用户审阅本计划并选择当前会话直接实现或分任务子代理执行。
