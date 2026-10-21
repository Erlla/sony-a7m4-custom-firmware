# 自定义声音测试音频

[English](README.en.md) · [自定义声音功能与集成方法](../../methods/06-custom-sounds/README.md)

提供 `YEAH.WAV`、`DAGOU.WAV` 和 `JIAO.WAV` 三个参考与测试音频。文件由用户提供并明确授权公开，保持原始字节，没有重新编码、归一化或调整音量。音频的授权说明见[第三方说明](../../THIRD_PARTY_NOTICES.md#reference-sound-samples--参考音频)；仓库原创代码的 MIT 许可不自动适用于这些音频。

## 导入到相机

需要先具备已集成的自定义声音功能；复制 WAV 本身不会安装该功能。完整固件的集成前提见[方法说明](../../methods/06-custom-sounds/README.md)。

1. 下载选定的 WAV 原文件，复制到 SD 卡的 `PRIVATE/SONY/PRO/SOUNDS/` 目录。
2. 在“拍摄 → 快门/静音”中进入“自定义电子快门声”或“自定义对焦声音”，将开关设为“开”。
3. 选择“从 SD 卡内导入”，选中一个文件并确认；成功保存后，菜单显示所选文件名。两个声音槽各选择一个 WAV，可使用相同或不同文件。

区分两种事件时，用 AF-S 只半按测试合焦声，再切 MF 电子单拍测试独立快门声。保持静音关闭；合焦声测试还需开启原厂对焦提示音。音量 50% 对应本功能基准增益，100% 对应两倍数字幅度。不同源音频的主观响度不一定相同。

## 文件参数与校验

三个文件均为整数 PCM（格式 1）、44,100 Hz、16 位、双声道，符合解析器的单文件 1 MiB / 5 秒限制。表中时长由 PCM 帧数计算；相机导入列表不显示时长列。本次发布核验了文件格式和完整性，没有新增机内测试结论。

| 文件 | 字节数 | PCM 帧数 | 时长 |
|---|---:|---:|---:|
| [YEAH.WAV](YEAH.WAV) | 196686 | 49152 | 1.115 s |
| [DAGOU.WAV](DAGOU.WAV) | 86094 | 21504 | 0.488 s |
| [JIAO.WAV](JIAO.WAV) | 86094 | 21504 | 0.488 s |

精确参数及 SHA-256 保存在 [manifest.json](manifest.json)。在仓库根目录可运行：

```powershell
Get-FileHash .\examples\custom-sounds\*.WAV -Algorithm SHA256
```

| 文件 | SHA-256 |
|---|---|
| YEAH.WAV | `01a907cdc8576dbc7b955ddc90b8e116e52ca634c5ad5d4482c3a79dc030cf5f` |
| DAGOU.WAV | `8ab0b01ef8361e5fc3c53e800dbd4572eec437aa3c163ab58e1b45d707b023ca` |
| JIAO.WAV | `c48b70b49e64cb64a4ceb19efb5f912d542c2255f369ca99f48882716a465ebe` |
