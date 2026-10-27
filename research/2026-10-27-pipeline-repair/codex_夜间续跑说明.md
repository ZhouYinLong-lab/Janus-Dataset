# Codex 夜间续跑（2026-10-28 02:30）

## 机制

- Windows 计划任务 `Janus-Codex-Resume`，触发时间 2026-10-28 02:30（Codex 额度 02:26 恢复）。
- 执行 `start_codex_resume.cmd`：从 `codex_handoff_prompt.md` 读取指令，通过 stdin 交给 Codex CLI。
- 使用应用自带的 `C:\Users\26585\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.exe`（0.164.0），因为 PATH 上的 npm 版 0.133.0 不支持 `gpt-5.6-luna`。
- 参数：`exec -s workspace-write -c approval_policy=never -`，工作目录为仓库根。
- 输出追加到 `local/codex_resume.log`；退出码同样写入。

## 已验证

- 任务状态 Ready，NextRunTime 2026/10/28 2:30。
- 手动执行一次 launcher：成功读取提示词并调用 CLI，当前因额度用尽返回 usage limit，日志与退出码写入正常。

## 取消或修改

```powershell
schtasks /Delete /TN Janus-Codex-Resume /F
```

换机器或换 Codex 版本时，改 `start_codex_resume.cmd` 里的 `CODEX` 路径并重新注册任务。

## 边界

- 任务以当前用户身份运行，需要保持登录会话；休眠不会触发。
- 指令要求不 push、不重置账本、不提交密钥与原文。
