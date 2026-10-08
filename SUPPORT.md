# 使用支持 / Support

先阅读 [项目说明](<README.md>)、[随包说明](<packaging/windows/README.txt>) 与 [beta.6 验收记录](<docs/releases/1.3.0-beta.6.md>)。当前桌面预发行基线是 1.3.0-beta.6；合并源码不自动把 beta 变成稳定版，也不表示全部商业发行验收已经完成。

## 下载与基本排查

- 从 [项目发布页](<https://github.com/ReactionForge/Pointer/releases>) 获取对应版本的安装 EXE 或便携 ZIP；使用同一版本的 SHA-256 文件校验。当前包未代码签名，哈希不能证明发布者身份，不建议关闭安全防护。
- 支持目标为 Windows 10/11 x64，发布包不要求另装 Python；核心光标功能可离线使用，更新检查和下载需要网络。
- ZIP 必须完整解压。首次应用成功后会部署到持久位置；安装/数据路径及商店宿主重定向说明见 [项目说明](<README.md>)。
- beta.3 的旧更新检查不会因新版发布自行修复；该版本用户需要手动下载安装新版一次，见 [beta.6 验收记录](<docs/releases/1.3.0-beta.6.md>)。

## 常见行为并非故障

| 现象 | 说明 |
| --- | --- |
| 改了参数，系统光标没有变化 | 预览为草稿；显式“应用更改”后才启用系统光标效果。侧栏外观保存与光标应用是两套状态。 |
| 关闭设置窗口后仍有动效 | 已启用的后台效果继续工作；需要时使用暂停或“恢复 Windows 原光标”。暂停与开机启动互相独立。 |
| Windows 10 看不到真正背景模糊 | host backdrop 只在受支持的 Windows 11 环境使用；不支持、失活、高对比或透明效果关闭时回退。 |
| 某些软件中的抓手或文本竖线没变化 | 第三方软件可能自行绘制光标；闪烁文本插入竖线由应用控制，不属于系统光标主题。 |
| 初次应用自定义配色需要等待 | 冷生成仍可能需要等待资源和服务就绪；历史本机时间不是所有机器的性能保证。 |

不要为排查删除最初光标备份、清空用户数据、清除 Windows 全局图标缓存或反复改写启动项。升级应保留用户设置；卸载前应恢复原光标，恢复失败会中止卸载。涉及恢复失败时先保存脱敏证据并联系维护者，不强行绕过保护。

## 报告问题

使用 [GitHub Issues](<https://github.com/ReactionForge/Pointer/issues>)。建议提供：

1. Pointer 完整版本、下载来源、安装 EXE 或便携 ZIP。
2. Windows 版本、显示器数量及缩放比例；界面深浅主题与相关设置。
3. 最短复现步骤、预期/实际结果、是否每次出现。
4. 脱敏截图或日志片段；标明是否只在第三方自绘光标中出现。

[项目说明](<README.md>) 列出了 `--diagnose` 与隔离目录参数。诊断报告可能含安装目录、用户路径等信息，提交前先自行检查并脱敏。不要上传完整用户数据目录、原光标备份、私人桌面内容或凭据。

安全漏洞按 [安全报告说明](<SECURITY.md>) 私密处理。商业授权、资产来源及稳定版就绪问题按 [商业化就绪评估](<docs/commercial-readiness.md>) 核验，不能把可下载解释为获商业使用许可。

支持通过仓库协作进行；这里不承诺实时客服、响应时限、免费定制、全部设备兼容或服务 SLA。

**English:** Report reproducible, redacted issues through GitHub. Include the exact version and Windows/display setup. Draft previews are not system changes; real backdrop blur requires a supported Windows 11 environment. This preview has no support SLA or commercial-clearance guarantee.
