# Codex 夜间续跑（2026-10-28 02:30）

## 机制

- Windows 计划任务 `Janus-Codex-Resume`，触发时间 2026-10-28 02:30（Codex 额度 02:26 恢复）。
- 任务设置 `WakeToRun=True`，到点唤醒机器；交流/直流唤醒定时器均已启用（AC=1、DC=1）。
- 执行 `start_codex_resume.cmd`：从 `codex_handoff_prompt.md` 读取指令，通过 stdin 交给 Codex CLI。
- 使用应用自带的 `C:\Users\26585\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.exe`（0.164.0），因为 PATH 上的 npm 版 0.133.0 不支持 `gpt-5.6-luna`。
- 参数：`exec -s workspace-write -c approval_policy=never -`，工作目录为仓库根。
- 输出追加到 `local/codex_resume.log`；退出码同样写入。

## 模型

默认沿用 `config.toml` 的 `gpt-5.6-luna`（high）。可用模型（本机缓存）：`gpt-6.1-sol`、`gpt-6-astra`、`gpt-6.1-terra`、`gpt-6-sol`、`gpt-reserve`、`gpt-6-luna`、`gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna`。换模型在 launcher 里加 `-m <slug>`。

## 电源

- 交流电源：从不睡眠、从不休眠。
- 电池：30 分钟后睡眠，不自动休眠；唤醒定时器已启用，02:30 可唤醒。
- 若到点仍未触发，先查 `powercfg /waketimers`（需管理员）和任务历史。

## 已验证

- 任务状态 Ready，NextRunTime 2026/10/28 2:30，WakeToRun=True。
- 手动执行一次 launcher：成功读取提示词并调用 CLI，当前因额度用尽返回 usage limit，日志与退出码写入正常。
- 助手侧另建 02:30 会话提醒；它依赖 DSH 应用仍在运行。

## 取消或修改

```powershell
schtasks /Delete /TN Janus-Codex-Resume /F
```

换机器或换 Codex 版本时，改 `start_codex_resume.cmd` 里的 `CODEX` 路径并重新注册任务。

## 边界

- 任务以当前用户身份运行，需要保持登录会话。
- 指令要求不 push、不重置账本、不提交密钥与原文。
