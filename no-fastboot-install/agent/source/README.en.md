# M4 Agent 1.00 source

This is the independent Windows x64 Agent source snapshot for build `1.00-agent-20261110-r1`. The [official package](https://github.com/Erlla/sony-a7m4-custom-firmware/releases/tag/A7M4-Agent-ToolKit-V1.00) bundles its runtime; users do not need Python, Git or a compiler.

[中文](README.md) · [Agent entry](../README.md) · [operating prompt](../PROMPT.zh-CN.md) · [USB-only recovery](../USB_RECOVERY.zh-CN.md)

The native launcher exposes `--agent doctor`, `status`, `start`, `resume` and `recover-usb`; the packaged Python backend performs the existing patch/recovery workflow. For USB-only recovery query `status` first, then follow the recovery commands: `doctor` may create a patch confirmation. Use returned job/request IDs, obtain user confirmation before writing, and query the original job after interruption. Do not delete state or repeat writes to clear a failure.

## Build and test

From this directory on a development Windows PC with Python 3.12+:

```powershell
py -3 -I -B prepare_assets.py --download --cache D:\M4-cache --output D:\M4-assets
py -3 -I -B build.py --assets D:\M4-assets --output D:\M4-build
py -3 -I -B tests\run_offline.py --source-only --report D:\M4-source-tests.json
```

For offline asset export use `prepare_assets.py --from-package <trusted.zip>` instead of `--download`. Pinned runtime assets are separate from source. See [build/release checks](RELEASING.md), [offline testing](tests/OFFLINE.md), [dependency notices](THIRD_PARTY.md) and [source provenance](SOURCE.json).

No package is rebuilt or replaced merely by publishing this snapshot. App, launcher, build code and dependency locks retain the released build's content; documentation and downloader tests are adapted to this location. Source/offline success does not establish clean-Windows, elevated-driver or physical-camera acceptance. macOS remains unavailable for writes. Desktop source is retained separately in [software](../../software/README.md).
