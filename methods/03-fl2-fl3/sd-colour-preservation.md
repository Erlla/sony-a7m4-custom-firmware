# SD 更新后 FL2/FL3 颜色数据丢失的修复 / SD colour preservation

**SD 更新及恢复更新必须使用索尼原厂电池。副厂电池显示补丁不改变此要求。** / **Use an original Sony battery for SD updates and recovery updates, including with the battery patch installed.**

## 原因与处理

SD 更新不仅替换 AP/CP，还按更新器的配置迁移路线处理 BK4 设置。早期包的32份通用默认模板未补入 FL2/FL3 颜色字段；已启用 LOOK 的机身经过迁移后，BACKUP.BIN/BAK 可缺少对应色度、映射和矩阵数据。因此菜单出现 FL2/FL3 并不证明三份颜色配置已正确部署。

公开构建器现在在精确官方 A7M4 6.02 明文基线中修复全部 LS/LS_GLEE 各16份模板，更新 `0111_backup_sum/backup.sum` 中32项 CRC，随后沿原构建链加密、签名、完整重解码。它复用了已经解决问题的研究方案，未将其他研究分支功能自动带入发布库。

| 字段 | 处理 | 保留边界 |
|---|---|---|
| CC1 `0x02A40001 + 0x1236` | 四字节映射22、24、23、25 | 其余映射和原有外观不改 |
| block13 `0x02A4000D + 0x1CC` | 相同四字节映射 | 同上 |
| CC1 bank22–25，`0x1250 + bank*64` | 各48字节，FX2绝对系数转为B、A1−B、A2−B | 各bank尾16字节保留；M4格式标志必须为0 |
| block13 bank22–25，`0x1E0 + bank*0x300` | 默认取每bank自己的192字节A1重复三次，B=A1=A2 | 各bank尾192字节保留 |
| BK4段校验和、backup.sum | 重算受影响段byte sum及全部32项模板CRC32 | 文件长度、TAR布局、索引与属性保留 |

每份恰好十个颜色字段，共2504字节；不写六条 LOOK 默认槽、reset数据或机身校准，不嵌入个人 nfa2/nfa6。供体CC1/block13必须匹配配方完整SHA-256；只接受零值、精确目标值或已知旧动态/固定矩阵，遇到未知非零字段、坏校验、重复颜色记录、缺模板或坏CRC立即拒绝。

代码：[sd_templates.py](../../a7m4/sd_templates.py)、[firmware.py](../../a7m4/firmware.py)；回归测试：[test_sd_templates.py](../../tests/test_sd_templates.py)。独立整包检查器同时核验32项模板CRC：[verify_sd_package.py](../../tools/verify_sd_package.py)。

## 构建和安装

沿[方法3的完整流程](README.md)取得本机备份和哈希正确的FX2供体，先构建组件，再构建SD包。打包命令新增必填 `--fx2-cc1` 与 `--fx2-block13`，默认 `--matrix-mode fixed-a1`；必须与组件manifest的模式一致。`dynamic`仅作为显式研究对照，不自动切换。

```powershell
# $ReleaseVersion 由统一发布流程明确设置为 X.YY
python -m a7m4.firmware build-fl23 --official local/M4-Ver.6.02.DAT --components output/fl23-components --fx2-cc1 local/fx2-color/cc1.bin --fx2-block13 local/fx2-color/block13.bin --public-key keys/published/A7M4_updater_public.pem --private-key keys/published/A7M4_updater_private.pem --version "$ReleaseVersion" --output output/fl23-sd
```

`verification.json` 新增 `sd_colour_templates`，列出32份源/目标哈希和保留边界。更新后仍应回读活动颜色区、BACKUP.BIN、BACKUP.BAK，核对十处字段与六个 LOOK，并检查 eMMC/物理 NOR CP 一致；不能把构建成功等同于实际写入或 NOR 同步。已有异常状态从最新本机回读生成局部修复，不能刷回别人的整设置区或直接覆盖旧快照。

## 证据与适用范围

| Evidence | Finding | 验证范围 / Path |
|---|---|---|
| [公开离线复现](../../docs/sd-colour-preservation-validation-20261018.json) | 32份真实官方模板的字段修复与已验证研究输出逐字节一致 | 精确源/供体哈希→十字段合并→模板与CRC复核；未生成新可安装DAT、未操作相机 |
| 同文件中的既有迁移证据摘要 | 研究基线的UUD2选择`-r`/mode5，已有LOOK保持；BIN/BAK保存模型通过 | 原迁移/保存函数，有建模OS/VFS/锁边界；不等于完整硬件仿真或所有固件路径 |
| [固定条件实拍报告](../../docs/fl23-colour-comparison-20261018/README.md) | 更新后的当前配方产生FL2/FL3效果，且有可量化残差 | 用户安装后的本次固定条件样片；不替代本次公开构建器的新整包实机验收 |

本方案针对**已完成启用、受支持迁移路径中的颜色保持**，不承诺全原厂首次安装、恢复出厂或任意UUD状态都自动启用 FL2/FL3。LOOK默认槽故意保留；首次安装、恢复出厂后的启用和其他更新器版本仍按方法3单独核验。公开源只含修复算法、测试和报告，不含供体颜色原始数据或完整固件。

## English

The SD updater migrates BK4 configuration as well as installing AP/CP. Earlier generic defaults omitted the new look colour fields, so an already-enabled camera could retain FL2/FL3 names while losing colour data in its saved configuration. The builder now patches all32 official LS/LS_GLEE templates with ten fields (2504 bytes each) and updates their CRC32 entries in `backup.sum` before the existing encryption/signing/full-decoding flow.

Each bank22–25 gets converted B/(A1−B)/(A2−B) chroma coefficients and its own A1 repeated across the three matrix endpoints. Only these fields and affected BK4 checksums change. LOOK defaults, reset data, attributes, remaining calibration, file sizes and TAR layout stay intact. No personal partitions are embedded. Exact donor hashes, known preimages and the complete32-template set are mandatory. Wrong inputs fail before package writes. The explicit matrix mode must match the component manifest.

This repairs colour preservation for already-enabled looks under the reviewed migration route. It does not promise activation after factory reset, every UUD state or compatibility with unreviewed firmware. Existing native migration/save evidence models OS boundaries and is not physical persistence proof. New publication tests do not constitute a new full-package camera acceptance. Read back all three colour copies, LOOK slots and physical NOR/eMMC CP after installation. Use the linked complete installation guide and an original Sony battery.
