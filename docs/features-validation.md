# 方法4/5与颜色说明：验证边界 / Methods 4/5 validation limits

日期 / Date: 2026-10-15. 机器可读结果见 [features-validation-results.json](features-validation-results.json)。

本次发布分别增加副厂电池和副厂镜头方法。**对焦速度限制修改未经过实机测试；当前 FL2/FL3 移植滤镜颜色与索尼官方版本存在差异。** 这两项说明同时出现在中英文 README、独立方法首页和构建报告中。 / This release adds separate battery and lens methods. **Focus-speed restriction removal is untested on hardware. Current FL2/FL3 port colors differ from Sony's official version.** These notices are retained in both READMEs, method guides and build reports.

## 当前离线检查 / Current offline checks

- 100项自动测试通过，包括原备份/恢复边界，以及新配方的前像、整文件身份、越界/重叠/长度/摘要错误拒绝、精确回滚和默认不启用额外功能。 / 100 automated tests passed, covering existing backup/restore boundaries plus new recipe identity/preimage checks, invalid bounds/overlap/size/hash rejection, exact reversal and explicit feature selection.
- 两种电池 AP 与两种镜头 CP 的正向/回滚均逐字节恢复源文件。电池每种60字节差异，镜头每种52字节差异；历史6.13 CP补丁后与原6.14/6.15功能产物逐字节一致。 / All four profiles reverse exactly; battery deltas are 60 bytes and lens deltas 52 bytes. The historical CP profile reproduces the original 6.14/6.15 feature artifact exactly.
- Thumb BL 独立解码证明五处新调用均指向helper、原调用均指向旧getter。20组合成标志/配置执行真实34字节helper，验证自动类别条件、未知值保留、R1..R12/SP/LR及源状态不变。 / Independent Thumb decoding checks old/new destinations. Twenty synthetic flag/configuration combinations execute the 34-byte helper and verify results, preserved registers/stack and unchanged source state.
- 新公开FL2/FL3 CP基线只增加同一52字节增量。相关四段代码与历史6.13相同，六处前像与已有执行映射已核对。**没有把6.13历史全套回放自动算作此新基线的全套验收。** / The newly bound public CP profile uses the same 52-byte delta; related code ranges, preimages and existing execute mapping were compared. Historical full-baseline validation is not automatically transferred to it.
- 使用真实 ext/FAT 镜像作为离线 fixture，检查两种分区编辑的长度、目标程序摘要、其余分区字节不变及逐字节回滚。这些fixture来自DAT成员，不冒充完整物理分区备份。 / Real ext/FAT member fixtures check unchanged length, program identity, unrelated bytes and exact partition reversal. They are not represented as complete physical backups.
- 显式选择 `--battery --lens-af` 构建本地组合SD包。独立struct解码器检查739,727块，与754,521,088字节明文逐字节相等，RSA、DEND、头CRC、五项part_image和一项updater CRC通过。新包只作本地离线验证，不发布/刷写。 / A local explicitly selected combined package passes independent block/plaintext, RSA/DEND/header and six-image CRC checks. It is not distributed or flashed.

## 不能由这些检查得出的结论 / What these checks do not establish

它们不证明镜头真实速度提高、固定FPS、AF-C/连拍表现、全部第三方电池兼容、提示在完整机内流程消失或官方色彩一致。 / They do not establish physical speed/FPS gains, AF-C/burst performance, universal battery compatibility, caution removal in every complete camera workflow or official color equivalence.

历史电量显示的一般用户反馈和历史6.15“使用中未遇到问题”保留为有限反馈，不能覆盖新的提示验收或镜头速度对照测试。没有新增设备访问、串口控制台或自动刷机。 / Historical user feedback remains limited; general operation is not acceptance of the new caution paths or physical lens acceleration. No device I/O, UART console or automatic flashing was added.
