# 光标资源

| 目录 | 用途 | 是否进入正式安装包 |
| --- | --- | --- |
| `cursors/adaptive/light` | 浅底黑主体、白边框 | 是 |
| `cursors/adaptive/dark` | 深底白主体、黑边框 | 是 |
| `cursors/adaptive/click/light`、`dark` | 箭头和小手的 4 档缩小帧，共 16 个文件 | 是 |
| `cursors/reference` | 固定黑主体、灰白边框 | 是 |
| `cursors/legacy-invert` | 历史原生反色实验 | 否 |

每套均有 17 个 Windows 系统角色，加载和后台加载使用 24 帧 ANI。CUR 包含多个 DPI 尺寸。

从仓库根目录安装绘图依赖后运行工具：

```powershell
.\.build-env\Scripts\python.exe -m pip install -r requirements/art.txt
.\.build-env\Scripts\python.exe -m tools.generate.create_cursor
.\.build-env\Scripts\python.exe -m tools.generate.create_hand_cursor
.\.build-env\Scripts\python.exe -m tools.generate.create_extra_cursors
.\.build-env\Scripts\python.exe -m tools.generate.create_dual_contrast
.\.build-env\Scripts\python.exe -m tools.generate.create_click_cursors
.\.build-env\Scripts\python.exe -m tools.verify.verify_dual_contrast
```

生成工具写入本目录，预览写入 `docs/images/`。原生验证检查纯黑白配色、热点、复制后的静态形状和动画帧；不会修改系统光标设置。

实验资源可用 `python -m tools.generate.create_adaptive_cursors` 重新生成，验证入口为 `tools.verify.verify_adaptive_cursors`。
