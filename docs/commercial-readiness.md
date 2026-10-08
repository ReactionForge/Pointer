# 商业化就绪评估 / Commercial readiness

> 结论：Pointer 1.3.0-beta.6 是可供后续商业迭代的预发行基线，不是已获商业授权或完成商业发行验收的产品。维护者目前不能确认全部素材权利；本次文档不授予 MIT 或其他项目许可，也不宣称商业使用已获许可。合并分支不等于解决权利、签名或质量阻塞。

功能与限制以 [项目说明](<../README.md>)、[beta.6 验收记录](<releases/1.3.0-beta.6.md>) 和 [随包说明](<../packaging/windows/README.txt>) 为依据。以下是待核验清单，不是法律意见或第三方合规认证。

## 权利清单：已见证据与缺口

| 对象 | 仓库中的可核验来源 | 尚未证实 / 商业发行前要求 |
| --- | --- | --- |
| 项目代码 | [项目元数据](<../pyproject.toml>)、[源码](<../src/pointer/>) | 当前 [项目元数据](<../pyproject.toml>) 未声明项目许可证。确认作者、贡献者及可分发权利，明确代码授权范围；依赖许可不自动成为项目许可。 |
| 光标造型、动效、CUR/ANI | [资源说明](<../assets/README.md>)、[箭头绘图](<../src/pointer/cursor/art/arrow.py>)、[手形绘图](<../src/pointer/cursor/art/hand.py>)、[角色目录](<../src/pointer/cursor/art/catalog.py>)、[光标资源](<../assets/cursors/>) | [随包说明](<../packaging/windows/README.txt>) 明确写有“依据参考截图重绘”。代码绘制不等于参考图或衍生造型权利已获确认；记录原始参考、作者、许可、适用地域及商用/改作/传播范围，无法证明时替换或取得书面许可。保留历史资源同样需要核验。 |
| 品牌主图与图标 | [主图](<../assets/icon_master.jpg>)、[生成脚本](<../scripts/generate_icon.py>)、[PNG 图标](<../assets/pointer.png>)、[根图标](<../pointer.ico>)、[随包图标](<../packaging/windows/pointer.ico>) | [生成脚本](<../scripts/generate_icon.py>) 优先裁切 [主图](<../assets/icon_master.jpg>)，缺失才使用程序绘制；不能据此证明现有 [主图](<../assets/icon_master.jpg>) 来源或商用权利。核验原始创作者、素材/生成服务条款、参考输入及商标风险；检查所有衍生尺寸。 |
| 勾选图形 | [生成脚本](<../scripts/generate_icon.py>)、[勾选图](<../assets/check.png>) | [生成脚本](<../scripts/generate_icon.py>) 包含程序绘制实现；仍需确认相关代码贡献权利，不单凭简单造型给出“已清权”结论。 |
| 历史 UI 提案与截图 | [图像目录](<images/>)、[UI 提案记录](<design/apple-ui-prompts.json>)、[光标家族提案记录](<design/cursor-family-prompts.json>) | 记录中有 built-in imagegen 提案和未批准、非成品软件标识。核验生成条款、参考输入和传播权利；不把生成提案当真实产品截图，也不暗示 Apple、Microsoft 或其他厂商背书。 |
| 视频画面、字体、音频 | [宣传制作约束](<launch-kit.md>)、[现有 Material 窗口](<../src/pointer/ui/material_workspace.py>) | 实际界面及项目光标艺术仍承接上述权利缺口。系统字体可渲染不等于可以再分发字体文件；留存字体视频使用依据。不默认添加音乐、素材库片段或配音；新增时分别取得录制、同步、传播等所需许可。 |
| 第三方代码及运行库 | [运行依赖](<../requirements/runtime.txt>)、[构建依赖](<../requirements/build.txt>)、[第三方声明](<../packaging/windows/licenses/THIRD-PARTY.txt>) | 当前固定 Pillow 12.3.0、PySide6-Essentials 6.11.2、PyInstaller 6.22.3；核对成品实际包含的 Python、Shiboken6、Qt 插件及间接依赖，不以依赖清单代替成品清单。 |

建立逐项权利台账：对象及哈希、原作者/权利人、来源 URL 或合同、许可版本、引用与署名要求、分发/改作/商业推广范围、审核人及审核日期。证据原件保留在受控私有位置；公开台账不得泄露合同、账户或私人机器路径。不能确认的项标为“未解决”，不是“默认可商用”。

## Qt / LGPLv3：交付义务待成品核验

[第三方声明](<../packaging/windows/licenses/THIRD-PARTY.txt>) 记载 Qt 与 Qt for Python 按 LGPLv3 使用、未修改共享库，并给出对应上游源代码链接。相关文本为 [LGPLv3](<../packaging/windows/licenses/LGPL-3.0.txt>)、[GPLv3](<../packaging/windows/licenses/GPL-3.0.txt>)、[Qt 第三方声明](<../packaging/windows/licenses/Qt-ThirdParty.html>) 与 [PySide 第三方声明](<../packaging/windows/licenses/PySide-ThirdParty.html>)。这些现有声明是合规工作的起点，不是已完成审计的证明。

商业分发不一定要求把整个应用改为 LGPL；必须选择并落实适用的合规路径：

- 每份发行物随附 LGPL/GPL 文本、显著使用声明、必要版权及第三方署名；检查安装包和便携包都实际含有这些内容。
- 按分发方式履行所含 LGPL 库的对应源代码义务，包括实际版本、补丁及构建信息。确认上游链接有效且所选提供方式满足适用条款；不得仅因为放了链接就认定所有源代码义务完成。
- 核验 LGPL §4 的共享库替换/重链接路径：用户能使用接口兼容的修改版库运行应用。实际验证动态库替换及所需说明，不仅检查目录存在；如选择另一合规路径，提供相应应用代码/材料与重组合条件。
- 应用许可、商业条款与技术措施不得禁止为了调试 LGPL 库修改而进行的逆向工程，也不得阻止修改相关库；在适用时提供安装信息。
- 审核 Qt 各模块、插件及第三方子组件的实际许可。若以后加入仅 GPL 或商业授权模块、静态链接或修改库，重新评估，不能沿用当前结论。
- 代码签名和安装/更新策略不得使兼容修改版 LGPL 库无法使用。由维护者与合格法律顾问对最终渠道和条款确认。

Python、Pillow、PyInstaller 的实际通知和例外也需随包保留；PyInstaller bootloader 例外不解除其他依赖的义务，也不解决项目艺术素材权利。

## 发布阻塞：签名与实机 QA

[beta.6 验收记录](<releases/1.3.0-beta.6.md>) 明确指出发布包未代码签名。SHA-256 只校验与预期文件的一致性，不证明发布者身份，也不保证没有 SmartScreen 提示。

面向商业稳定版前，应确定发布主体、签名证书及私钥保护、时间戳、签名校验、密钥泄露处置与版本撤回路径。记录最终安装包和主要可执行组件的签名状态；未解决前如继续提供预览包，必须明确标为未签名，而不是诱导用户关闭安全防护。

[beta.6 验收记录](<releases/1.3.0-beta.6.md>) 保留历史测试证据，并明确以下仍待实机验收：

- 新安装后桌面图标、真实系统光标按下/长按/松开效果；不能用渲染视频代替。
- Windows 10/11、混合 DPI、跨屏、Snap、窗口拖动、最大化/还原及边缘调整大小。
- 真实高对比切换、系统透明效果策略与受支持/不支持合成环境；长时间 GPU、功耗及远程桌面表现。
- 最终产物安装、保留配置升级、卸载恢复、失败回退；原始光标备份保持不变，未变化启动项不重写。

真正 host backdrop 仅适用于受支持的 Windows 11 环境；Windows 10 等环境回退。离屏布局图与原生桌面合成证据必须分开，参见 [背景历史记录](<design/material-window-iteration.md>)。本机历史性能数字不得宣传为所有设备的保证。

[现有发布流程](<../.github/workflows/release.yml>) 配置了源码测试、新包诊断、隔离包生命周期和安装器检查；配置存在不代表本次产物已经运行通过。以最终提交与产物哈希对应的结果为准，明确跳过项。

## 有条件的商业化放行清单

- [ ] 项目代码授权及贡献权利经维护者确认；全部待发布资产可追溯，无法证明权利的已替换或获许可。
- [ ] 成品依赖清单、许可证与对应源码义务经核验；LGPL 修改库运行路径有操作说明和测试证据。
- [ ] 最终商业条款、隐私说明、收费/退款和渠道规则已按实际商业模式审核。这里不预设价格、付费服务或数据收集行为。
- [ ] 最终安装包和便携包通过源码全套测试、冻结程序诊断、隔离安装/升级/卸载与关键失败回退；保留原始备份和启动项证据。
- [ ] 上述实机 QA 矩阵完成；剩余限制公开，有负责人签字，不把模拟测试算作物理验收。
- [ ] 签名及时间戳方案落实，校验与撤回流程可用；未签名预览的风险已明确。
- [ ] 宣传中版本、支持系统、视频呈现方式和限制与最终产物一致；素材与音频另行清权。
- [ ] 支持、安全私密报告渠道及维护责任已明确；不存在编造客户评价、保证流量或保证性能。

**Only after these gates are satisfied may the maintainer assess commercial release. This document grants no license, confirms no asset clearance, and makes no certification or sales guarantee.**
