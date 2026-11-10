# M4 desktop and AI Agent 1.03

This is the canonical shared source for both Windows x64 packages. The desktop GUI and supported --agent commands use the same patch and recovery backend. [中文](README.md) · [Agent prompt](../agent/PROMPT.zh-CN.md) · [Build guide](RELEASING.md).

1.03 uses one PowerShell process for bounded PnP polling, retains one final snapshot, and gives desktop and Agent users a menu-only continuation after a proven pre-session connection stop. It preserves the original p1 run and old menu attempt, verifies the same body, and never dispatches a p1 writer for this continuation. USB recovery remains a separate option. Descriptor diagnostics retain the actual stage and backend error codes.

Version: 1.03. Agent build: 1.03-agent-20261111-r1. Independent Agent 1.00/1.01 stopped-menu records can be reopened in their original directory; unknown or active legacy operations cannot be replayed. Firmware compatibility checks, full backup and independent readback are unchanged.

See README.md and RELEASING.md for asset acquisition, building and offline verification. Runtime assets are locked separately; no private state, firmware or camera libraries are published. Offline tests do not establish clean-PC or physical-camera acceptance.
