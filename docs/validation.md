# 验证记录 / Validation

2026-10-21：新增[SD 更新救砖验证记录](../methods/00-sd-recovery/validation.md)。公开适配复用原有 FAT/fastboot 模块，离线核对恢复流程、连接错误、资源登记及 BAT 启动；没有操作相机，其他五项补丁配方未改变。 / Added public SD-recovery validation. The adaptation reuses existing FAT/fastboot modules, checks synthetic workflows/resources/launchers offline, and does not operate a camera or change the five patch recipes.

> 2026-10-17 更新：本文原日期和测试数为历史记录；FL2/FL3 固定 A1 的当前结果、残差及图片见[最新验证](../methods/03-fl2-fl3/color-validation-20261017.md)。旧版颜色差异提示不能覆盖该新证据。
> Update: the dated checks below are historical. Current fixed-A1 evidence and remaining limits are in the linked report; the earlier color notice does not describe the new matrix mode.

日期 / Date: 2026-10-15. 机器可读结果：[validation-results.json](validation-results.json)。

本页保留首次发布的81项测试及FL2/FL3包验证。新增方法4/5的最新100项测试、分区/组合包检查与未测试状态见 [新增方法验证](features-validation.md)。当时的动态矩阵样片与软件重选有差异；镜头对焦速度修改未经实机测试。 / This page retains the initial81-test release evidence. See [feature validation](features-validation.md) for the latest 100-test extension, filesystem/package checks and untested status. The earlier dynamic-matrix samples differed from software re-selection; lens speed effects have not undergone physical testing.

2026-10-15 新增镜头原版流程研究：[中文](../methods/05-third-party-lens-af/README.md) / [English](../methods/05-third-party-lens-af/README.en.md)、[回放脚本](../tools/replay_lens_af_flow.py)和[16组原生回放结果](../methods/05-third-party-lens-af/native-flow-results.json)。分别验证 ID 兼容过滤、请求/缓存/速度选择及描述符范围回退；范围类别和协议输入为合成数据，setter 参数传递显式桥接。它不修改现有补丁配方，不新增范围解锁，也不验证实机速度。 / Additional stock-flow research separates ID filtering from descriptor-based range fallback. The 16 original-instruction cases use synthetic inputs and an explicit setter-argument bridge. This does not change the patch recipe, unlock the range gate or validate physical performance.

## 首次发布源码验证 / Initial source release validation

- 在新的 Python 3.12 虚拟环境安装核心、测试和可选固件依赖；81 项自动测试通过。 / Installed in a fresh Python 3.12 environment; 81 automated tests passed.
- 合成相机测试覆盖完整备份门控、取消/短读/校验失败、会话过期、同机绑定、写前源变化、精确确认、写后整分区哈希、恢复约束和真实 Windows BAT 的中文/空格路径。测试不会接触设备。 / Synthetic transport tests cover backup gates, failure/cancellation, session invalidation, content binding, stale sources, exact confirmation, full readback, restore restrictions and the actual Windows BAT with localized/spaced paths. No hardware is contacted.
- BCD 明确向量包括 0.00、6.09、6.10、6.15、6.20、9.99；非法旧编码拒绝。 / Known BCD vectors and invalid existing encodings are checked.
- 模拟桥覆盖 uart_boot 1/2 与未知版本拒绝；断言只使用命令 1–5，未提供交互 UART 发送命令 6。 / Mock bridge checks cover both supported handshakes, refusal of unknown versions and use of commands1–5 only, without interactive UART transmit command6.
- 独立构造的 BK4/UFU fixture 验证索引、长记录、颜色差分转换、其他段保留、校验错误拒绝、无修改重编码逐字节一致、改写后完整重解码及 RSA 签名范围。 / Independently constructed fixtures exercise BK4 indexing/long records, coefficient conversion, unrelated segments, invalid checksums, exact no-op re-encoding, modified roundtrip and signing ranges.
- 使用本地自有样本重建，AP 与 CP 的完整 SHA-256 分别匹配已核验目标 `d17e61…bdd8ff` 与 `4551c7…3b3479`；机身配置编辑结果与历史 v6 核验产物逐字节一致，nfa6 原有已部署颜色数据保持不变。个人镜像和个人数据哈希未公开。 / Local owned inputs reproduce the exact reviewed AP/CP targets and historical v6 settings result. Already-deployed nfa6 color data remains identical. Personal images and their hashes are not published.
- 从官方 6.02 重新构建自签SD验收包，修改四个镜像成员及两个清单，保留其余 TAR 成员；更新器四函数原始白名单、PEM 指纹、SquashFS 元数据回读通过。 / Rebuilt a custom-signed SD acceptance package from official 6.02; changed four images and two manifests, preserving other TAR members. Updater original-function allowlists, PEM identity and SquashFS metadata roundtrip passed.
- 额外使用 [verify_sd_package.py](../tools/verify_sd_package.py) 的独立 `struct` 解码路径，不导入构建器的 NumPy codec：739,727 块全部校验并与 754,521,088 字节明文逐字节比较；验证 RSA、DEND、头 CRC、全部五项 part_image 与一项 updater 镜像 CRC 和 WBI3 标志。 / An independent struct-based decoder, not the builder codec, verified all blocks, byte-compared the full plaintext, checked RSA/DEND/header CRC, all five part-image CRCs, the updater image CRC and WBI3.

可对本地构建重复独立检查： / Repeat the independent audit on a local build:

```powershell
python tools/verify_sd_package.py output/fl23-sd/BODYDATA.DAT --plain output/fl23-sd/work/plain.bin --public-key keys/published/A7M4_updater_public.pem --report local/package-audit.json
```

`decode` 自身报告 `rsa_verified=false` 仅表示其职责是解码/校验块；签名由签名器和上述独立审计分别验证。不能孤立解读一个字段为完整包验证结果。 / The decoder's `rsa_verified=false` means that stage does not authenticate signatures; the signer and independent audit verify RSA separately. Read the complete verification results together.

## 历史实机与未知项 / Historical hardware evidence and limits

维护者历史机身安装过自签测试包。用户反馈确认 FL2/FL3 拍照/视频名称与颜色变化，2026-10-11 明确确认 FL3 更新后回放名称正确。 / Historical feedback confirms custom-signed test package installation, shooting/movie names and color changes, and correct FL3 playback after the 2026-10-11 update.

这次新主机工具和本次重新构建包**没有连接或刷写相机**。以下未自动转记为通过：更新后 FL2 回放、原始 MakerNote 值、物理 NOR/eMMC CP 哈希、全部持久化与特殊模式、恢复出厂后的默认槽、实体 FX2 像素对照、新上游 UF2/payload 的硬件兼容性。 / This extracted host and newly rebuilt package have not been flashed. Post-update FL2 playback, raw MakerNote fields, physical NOR/eMMC hashes, all persistence/special modes, factory-reset slot defaults, pixel comparison to FX2 and newly built upstream payload compatibility remain unresolved hardware checks.

源码检查和测试通过不是安全刷机保证，也不意味着任意机身/固件通用。 / Passing offline checks is neither a flashing safety guarantee nor compatibility with arbitrary cameras/firmware.

## 自定义电子快门声与对焦声 / Custom sounds

[独立方法与限制](../methods/06-custom-sounds/README.md)、[具体修改方法](../methods/06-custom-sounds/IMPLEMENTATION.md)、[机器可读验证](custom-sounds-validation.json)。公开 65 份原生输入，六模块编译及最终安装段核对、71 个文件重建、32 项 C 核心检查和 Python 拒绝路径/输出保护检查通过。参考 AP 已有共享菜单框架，不能直接套用原厂 AP；本方法不改机身报告版本，也未自动加入完整 SD 构建器。

既有单机功能构建获用户确认所需功能正常；公开文件配方另有离线原生回归，未补写新的机内验收。新地址布局、完整包集成和跨机身可靠性没有因公开整理而自动通过。本次没有操作相机或生成新可安装固件。

The published native source reconstructs six modules and the recipe reproduces71 exact reference-layout files.32 C core checks and Python safety/rejection tests run without a camera. Existing single-camera functionality has user acceptance; the published reference files have offline checks, not a separate new hardware acceptance. Display versions are neither changed nor used as compatibility keys. Stock AP and arbitrary combinations remain unsupported by this reference recipe.

### 合并菜单文字资源修复 / Merged menu resource repair

[资源修复方法](../methods/06-custom-sounds/menu-resource-repair.md)补充独立的68文件修复配方及最终文件系统检查。修复目标与原完整声音配方相同；只输出文字资源，保留已合并AP／CP／MPR、LUT和版本字段。维护者资源独立修复已获用户单机实测确认，不自动扩大到完整参考程序或任意基线。新CLI另经本地真实文件重建与合成数据拒绝／完整性测试；记录见 [menu resource validation](custom-sound-menu-resources-validation.json)。

The resource-only repair has user acceptance on the maintainer's merged camera build. All68 resource outputs match the existing full recipe. Offline checks also cover final-filesystem verification, missing/corrupt bank rejection, idempotent repaired inputs and preservation of program/settings files. They do not emulate glyph rendering or certify other program combinations.

## 自定义纵横比 / Custom aspect ratios

2026-10-22：[方法7](../methods/07-custom-aspect-ratios/README.md)记录17:6、65:24、5:4、7:6的最终功能、JPEG/HEIF裁切与RAW原始幅面、比例文字/Fn图标及预览遮罩。维护者确认6.63 T22横竖屏预览正常，附两张65:24实机照片。部分参数设置页暂时显示3:2，返回拍摄页恢复所选比例遮罩；此项只涉及预览。

The maintainer accepted landscape and portrait previews on the 6.63 T22 camera build. [Method7](../methods/07-custom-aspect-ratios/README.en.md) documents the final behavior and two 65:24 camera examples. 336 native lifecycle cases, 3,475 drawing checks, 3,968 ABI checks and final package verification passed. JPEG/RAW geometry has sample checks; a separate measured HEIF sample is not included. This publication adds documentation and photographs without changing firmware or host programs.
