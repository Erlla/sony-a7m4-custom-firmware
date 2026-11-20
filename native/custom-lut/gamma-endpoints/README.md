# 自定义 LUT Gamma 可变末点

[源码补丁](source-changes.patch)适用于本项目的 M4 自定义 LUT 固件源码。照片和取景 Gamma 均可在原有 18 位数值范围内指定末点。记录仍须从零开始、非递减，末点须非零，且末点 Y 与记录内偏移 `0x220` 的 32 位小端控制值相等。采样分段和其余控制字段继续匹配各自的照片／取景模板。

AP JSON 导入与 CP 发布使用同一规则。强度混合沿用实际 Y 值与固定 ST 曲线的混合，并同步控制字中的末点。内部强度派生校验使用该强度可达的整数末点范围。旧滤镜保持相同的解码与混合结果。

## 应用

以本地匹配的 LUT 源码工作副本为当前目录，目录内应包含 `20261021/task28_p1_runtime_codec`、`20261023_p3_native_engine` 和 `20261027_p6_reclaim`。用现有构建链分别重编 AP 和 CP。

```powershell
git apply --check /path/to/source-changes.patch
git apply /path/to/source-changes.patch
```

适配 R5 CC 时，照片部分可以保留 `131071` 和前面的 128 个 Y 值。各记录仍需采用对应的 M4 控制模板、同步 `0x220` 并重算 `payload_sha256`。此源码变更需随 AP 和 CP 一起部署才会生效。

## English

The M4 LUT firmware accepts a record-defined Gamma endpoint in both photo and live branches. The curve must start at zero, be nondecreasing, and end at a nonzero 18-bit value matching the little-endian word at `0x220`. All other profile controls are checked as before. Apply the patch to the matching local LUT source tree and rebuild both processors. Existing release firmware still uses its fixed endpoints.
