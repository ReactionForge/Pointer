# 光标资源

`cursors/adaptive/light` 为浅底黑主体白边，`dark` 为深底白主体黑边；`click` 与 `tilt` 是默认大小的缩小和倾斜动效帧。`reference` 保留固定参考造型，`legacy-invert` 为历史实验资源，不进入安装包。

每套有 17 个 Windows 角色；加载动画含 24 帧。默认造型与热点保持兼容。APP 自定义资源保存在用户数据的缓存目录，不写入源码资源。

```powershell
python -m pip install -r requirements/dev.txt
python -m scripts.generate_cursors
python -m scripts.create_theme_preview
python -m scripts.verify.verify_animation
python -m scripts.verify.verify_dual_contrast
```

生成入口统一调用 `src/pointer/cursor/art`，原生检查只加载并绘制资源，不修改系统设置。默认箭头最大倾斜 6°，小手 12°；APP 强度可提升至其两倍。
