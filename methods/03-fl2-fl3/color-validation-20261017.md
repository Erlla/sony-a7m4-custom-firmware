# FL2 / FL3：当前颜色结论与实拍对照

2026-10-17。当前实现的 **FL2/FL3 外观数据与 FX2 原版供体一致**；默认固定各自 A1 后，本次机内直出与 Imaging Edge 重选外观颜色接近，旧版主要偏色已解决。这里的“一致”限定为所核验的外观数据和矩阵选择目标，不能改写成“两个 JPEG 完全没有差异”或“与实体 FX2 全场景等效”。

## 为什么之前不同

1. **比较用的参数不是同一组。** 解锁脚本使 A7M4 RAW 可在 Imaging Edge 中选 FL2/FL3，同时为备选外观写入 FX2 A1 矩阵。原相机走 B/A1/A2 插值，实拍常为 B 或接近 B。软件重新选择外观改用了 A1，因此会偏色；供体表存在不代表运行时已经选到同一矩阵。
2. **这一现象也存在于原有 FL。** 未解锁的原厂 FL 在“直接导出”和“切到 ST 再切回 FL”之间也改变颜色；只将该 RAW 主矩阵替换为它自带的 FL 备选矩阵，即可重现主要差异。不能单凭重选后不同认定新滤镜系数错误。
3. **部署必须闭环。** SD 更新迁移过设置，活动 nfa6 与 BACKUP.BIN/BAK 曾不一致；只线刷 nfa8 也不会同步独立 NOR。须核验四个 bank、三份配置、双处 CP 和正常开机后的持久化。
4. **一个 RAW 整数单位是另一层问题。** 固定 A1 后 FL2 的内部1614可在 M4 的 WB 定点往返写成1615，FX2 有直接写出分支。新候选在中性、主 RAW、校准保护条件下忠实写出原矩阵，未改 JPEG；有界离线验证不是新照片验收。该候选未合入公开6.02配方。

## 当前修改方法

`python -m a7m4.fl23 build` 默认 `--matrix-mode fixed-a1`。四个 bank22/23/24/25 分别对应 FL2照片、FL2视频、FL3照片、FL3视频；每个都将 B/A1/A2 设为本 bank 的原版 A1。CC1差分编码、Gamma、菜单及元数据补丁仍按[主方法](README.md)；保留本机白平衡和传感器校准。`--matrix-mode dynamic` 只保留原动态端点用于研究，不用于本次软件颜色匹配结论。

SD包不嵌入个人颜色/设置。SD更新后，用最新本机回读修复 nfa6、BACKUP.BIN、BACKUP.BAK 并重算BK4校验；核对六条槽值、eMMC和NOR CP，再正常重启回读。不能用旧整分区覆盖新版本/用户配置。本仓库仍只接受列出的原版6.02程序哈希，不会把6.24新代码误当原版处理。

## 两组新拍结果

图来自6.24固定 A1 安装后的新照片，**不是6.26 RAW写出候选安装后的照片，也不是两台相机对拍**。软件图由同一次 RAW 解锁后重新选择相同外观导出。曝光、镜头和图像载荷相配；当前EXIF为Auto WB，不能沿用早期4200K描述。新拍名称/编号为 FL2/22、FL3/23。

| 项目 | FL2 | FL3 |
|---|---:|---:|
| RAW主矩阵匹配A1 | 104/105；右下1615 vs 1614 | 105/105 |
| 780F中的96系数 | 96/96 | 96/96 |
| 平滑区域平均 ΔE76 | 1.0236 | 1.0041 |
| 中位 ΔE76 | 0.9205 | 0.9222 |
| R/G/B直方图重合 | 97.28/97.48/97.46% | 97.54/97.49/97.79% |

左为机内 JPEG，右为 Imaging Edge 重选；上 FL2，下 FL3：

![固定A1的FL2和FL3机内与软件对照](images/FL2_FL3_contact_sheet.jpg)

橙线机内，蓝线软件；上 FL2，下 FL3，依次 R/G/B：

![RGB直方图对照](images/RGB_histogram_comparison.png)

在1752×1168配准图上，用相同平滑区域掩膜和Lab D65欧氏ΔE76统计，没有拟合曝光、白平衡或颜色来拉近结果。直方图重合是逐桶取最小值后的总和，**不是97%的像素相同或综合色彩准确率**。两图仍有小幅明暗、颜色和细节差异；本轮不能唯一归因于压缩、锐化、DRO或矩阵舍入。RAW一个整数单位的修复也不能证明JPEG残差消失。

文件摘要、范围和指标见[机器可读证据](../../docs/fl23-validation-results-20261017.json)。当前仅每种外观一组新拍，未覆盖全光源/全部调节值、视频像素、恢复出厂或实体FX2同场景。构建器报告的 `fl23_color_matches_official=null` 表示“不作整体等效判断”；矩阵模式和现场验收须分别查看。

## English summary

The imported FL2/FL3 look data matches its stock FX2 donor. The current default fixes each of the four matrix banks to its own A1. The earlier mismatch mainly compared the camera's interpolated main matrix with an A1 alternate matrix injected by the RAW unlock script and selected by Imaging Edge. An unmodified stock FL control reproduced this distinction too. Configuration migration and independent CP NOR also require readback.

The photographs above are 6.24 fixed-A1 results, before installation of the RAW serialization candidate. Each pair compares an in-camera JPEG against Imaging Edge re-selection from the corresponding RAW, not against a physical FX2. Mean smooth-area DeltaE76 is1.0236/1.0041; neither pixel identity nor all-scene equivalence is established. FL3 matches all105 main-matrix values; FL2 matches104, with1615 vs1614 in7800. Original-instruction replay traces that unit to WB fixed-point serialization. A guarded RAW-only candidate exists but is not included in this public6.02 recipe and has not passed fresh-photo acceptance. The figures are published with source digests and without original RAW files.

代码检查：105项测试全部通过，无跳过；真实最新本机nfa2/nfa6离线重放零字节变化。见[代码验证](../../docs/fl23-code-validation-20261017.json)。测试不访问设备，也不是新DAT或新RAW的实机验收。
