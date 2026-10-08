# 安全报告 / Security

Pointer 会在用户显式应用后改变系统光标，并包含配置导入、后台运行、更新下载与安装流程。涉及这些边界、文件路径、进程通信或发布供应链的漏洞，请尽量私密报告。

## 私密报告方式

1. 如果仓库已启用 GitHub Private Vulnerability Reporting，请通过 [GitHub 私密漏洞报告入口](<https://github.com/ReactionForge/Pointer/security/advisories/new>) 发送。这里不保证该功能已启用或入口对所有账户可用。
2. 如果不可用，请在 [GitHub Issues](<https://github.com/ReactionForge/Pointer/issues>) 仅请求维护者提供私密安全沟通渠道。不要在公开 issue、PR、评论或附件发布漏洞细节、利用代码、密钥或私人路径；等维护者明确渠道后再发送详情。

未公布经核实的私密邮箱，不提供虚构联系方式。本项目没有在此承诺响应时限、修复时限、漏洞奖金或长期安全支持。

## 报告内容

私密报告中建议包含：

- 受影响版本、安装包或便携包、Windows 版本与最小复现步骤。
- 漏洞影响、所需权限/用户操作、预期与实际行为。
- 脱敏的堆栈、日志片段或最小示例；若提供包哈希，说明来源。
- 是否已经公开、是否有修复建议，以及方便后续协调的 GitHub 身份。

不要访问他人数据，不在未经授权的机器测试，不在真实用户环境执行破坏性安装/卸载或系统设置操作。复现需要系统改动时，先获得授权并采用隔离环境。

## 版本与分发边界

当前预发行基线及已知限制见 [beta.6 验收记录](<docs/releases/1.3.0-beta.6.md>)。本项目尚未发布明确的安全维护版本矩阵或补丁 SLA；不要假定历史稳定版、旧 beta 或源代码分支仍会获得修复，报告时请注明确切版本。

[项目说明](<README.md>) 与 [随包说明](<packaging/windows/README.txt>) 提醒当前发布包尚未代码签名。SHA-256 用于与发布的预期哈希比对，不能替代发布者身份验证；不要为了运行程序关闭 Windows 安全功能。签名、依赖许可及实机 QA 的商业发行阻塞见 [商业化就绪评估](<docs/commercial-readiness.md>)。

普通使用问题走 [支持说明](<SUPPORT.md>)。维护者确认私密渠道和处理计划前，不要假定报告会被保密、及时收到或及时修复。

**English:** Use GitHub private vulnerability reporting only if enabled. Otherwise, ask the maintainer for a private channel without disclosing exploit details publicly. No verified private email, response SLA, bounty or supported-version guarantee is stated here.
