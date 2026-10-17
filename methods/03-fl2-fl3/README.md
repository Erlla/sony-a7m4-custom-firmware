# 方法 3：FL2 / FL3 移植、刷入与 NOR 同步

[English](README.en.md) · [总说明与刷机风险](../../README.md)

此方法单独说明创意外观 FL2/FL3。**移植的 FL2/FL3 外观系数、对应矩阵端点和曲线取自 FX2 原版；当前默认将四组矩阵固定为各自 A1，以匹配 Imaging Edge 重选外观的目标。** 固定 A1 已有本机回读和新拍照片支持，旧版显著偏色的主要原因已消除；本轮样片平均 ΔE76 约 1.0，仍不宣称 JPEG 逐像素相等或与实体 FX2 所有场景等效。[实拍和参数验证](color-validation-20261017.md)。

**不能只改菜单，也不能只刷 `nflasha8` 就认为完成。** 完整组合涉及 AP、CP、颜色数据、配置副本与独立 CP NOR。

## 当前6.26 RAW验收与限定补丁

维护者本机6.26已经过eMMC/NOR完整CP比对、SD后仅nfa2的缺失配置恢复及正常开机后持久化检查。新拍的**原始**DSC02788_FL2、DSC02789_FL3均为主SR2的105/105项精确等于各自FX2 A1，FL2右下项现在为1614。[6.26证据](../../docs/fl23-626-validation-results-20261017.json)。新补齐的6.26软件重选JPEG平均ΔE76为FL2 1.0007、FL3 0.9754，仍有小幅残差；[6.26新图与完整指标](color-validation-20261017.md#626两组jpeg对照结果)。原6.24图和测量保留，不重标版本。

[RAW无损写出配方](../../a7m4/profiles/fl23/cp624-to626-raw-lossless-recipe.json)只接受完整CP SHA `acecf071…505b2`，生成`9e312f58…611b`，两段新代码/跳板共212个实际变化字节。源为保留其他修改的实验6.24，**不是**下表公开原版6.02/v7构建输出；不接受其他源，也不自动合入`firmware build-fl23`。

该分支只对FL2/FL3主RAW、对应selector、四WB增益>1024、identity辅助矩阵及中性校准/增益上限状态直接复制内部矩阵，保留额外矩阵/mode9/饱和尾部；其他状态回旧路径。它不改JPEG，不是硬编码把1615改1614。离线32组目标、33组回退和完整主链联调已覆盖，现又有两张新照片确认。

持有该精确源的用户可离线构建新CP：

```python
from pathlib import Path
import json
from a7m4.fl23 import patch_program
recipe = json.loads(Path("a7m4/profiles/fl23/cp624-to626-raw-lossless-recipe.json").read_text("utf-8"))
source = Path("local/CPAPP-B.experimental624.BIN").read_bytes()
patched = patch_program(source, recipe)
with Path("output/CPAPP-B.lossless626.BIN").open("xb") as output:
    output.write(patched)
```

这只生成CP文件。安装仍须保留同机现有修改、构建匹配自签SD包并同步独立NOR，更新后从新回读修复三份A1配置；不能只刷nfa8。完整固件和相机原始照片不随配方发布。

## 固定基线与公开产物

目标为 A7M4 **官方 6.02**，颜色供体为 FX2 **1.01**。程序按哈希识别，不能依赖可改写的菜单版本号。

| 文件 | SHA-256 |
|---|---|
| A7M4 6.02 官方 DAT | `ad6df47a0a93a46336b9920a0d8891d0c766f8c96fa68ebda8685f6c21621188` |
| 原厂 `appFw.so` | `1e1b9202eaa69198f20df03dbfdab2f103b206cc4ebcd2e7bd817e6a710018a2` |
| 目标 `appFw.so` | `d17e61fb4ba193d8e7d802196edff5f578d5691b3fcc4abcd1cbbb6e58bdd8ff` |
| 原厂 `CPAPP-B.BIN` | `7b9b137d696e5972d20db7f9119076172ed8e0730805d7f0b4c31b87689e2c2b` |
| 目标 CP（v7，16,236,816 字节） | `4551c73386c27a0a9b247fd3e05c3bd5e3425bdb9fe9f8374c201c96533b3479` |
| FX2 1.01 CP | `eba723db657117a36d9593dacf640840aca893c0d6ee5d728de9d1996b8c5e29` |
| FX2 CC1 | `c87f4dad18225b0b6a5a273bd27211fd93ad0ca0ab8ac2f1b65f680daec4d996` |
| FX2 block13 | `d783cf223304e67d6d671642c8b1102a0c663bc114a64c7f76a1d160d8a3feee` |

源码：[fl23.py](../../a7m4/fl23.py)、[firmware.py](../../a7m4/firmware.py)。精确配方：[AP](../../a7m4/profiles/fl23/ap-recipe.json)、[CP v7](../../a7m4/profiles/fl23/cp-v7-recipe.json)。配方包含原始字节哈希、位置及补丁，不包含完整索尼程序、供体曲线或系数。CP 的 20 项供体操作在用户本地读取并转换数据，416 段其余差分合计 1,595 字节；重建后核对完整目标哈希。

## 功能链与存储范围

| 外观 | AP 主枚举 / 槽 / look | CP color | 照片 selector / bank / gamma | 视频 selector / bank / gamma | CP 元数据枚举 |
|---|---|---:|---|---|---:|
| FL2 | 17 / 16 / 10 | 19 | 54 / 22 / 47 | 56 / 23 / 49 | 22 |
| FL3 | 18 / 17 / 11 | 20 | 55 / 24 / 48 | 57 / 25 / 50 | 23 |

AP 与 CP 的编号空间不同，不能互换这些数字。

| 位置 | 修改 |
|---|---|
| `nflasha15:/lib/appFw.so` | 开放已有文字/图标和菜单 flags、look 支持、look→CP color 路由 |
| `nflasha8:/CPAPP-B.BIN` | selector、gamma、矩阵/系数 gate、消费者、主/第二名称、属性枚举和加载属性 |
| 本机 `nflasha6` | CC1 / block13 中新增的映射、转换系数与矩阵 |
| 本机 `nflasha2:/BACKUP.BIN`、`BACKUP.BAK` | 两份颜色副本、六项槽配置和所有受影响 BK4 校验和 |
| 独立 CP NOR | 经匹配的官方更新脚本同步完整 CP；它不属于 eMMC 分区 |
| `nflasha1` | 自签包安装环境，信任匹配公钥；详见独立方法 1 |
| `nflasha5` | 当前组合将 `WBI2` 改为 `WBI3`，避免恢复旧暖启动快照 |

### AP 的五组修改

以下在本基线中 ELF VA 与文件偏移相同：`0x35E6258` 写 40 字节，把 look 10/11 发成 color 19/20；`0x3FDE5B4`、`0x3FDE634` 各 40 字节，把两行的 20 个 uint16 flags 设为 1；`0x4AB894A`、`0x4AB9B21` 各 2 字节，开放 look 10/11 与主枚举 17/18。实际变化 66 字节。旧 look 0–9 的转换保持，非法 look 12 仍拒绝。使用固件已有 FL2/FL3 资源，无需复制 FX2 整套 UI。

### CP 的完整 v7 修改

常规 CP 地址 = 文件偏移 + `0x108000`，不适用于把启动段表当执行地址。CP 实际变化 5,845 字节。公开配方覆盖 v7 第二名称补丁，也保留历史构建中留下的数据副本，不能只按旧 v5 清单重建。

| 数据块 | CP 文件偏移 | 内容 |
|---|---:|---|
| A | `0xA9B240` | 扩展 gamma 指针表及保留区，`0x5E0` 字节 |
| B | `0xA9B820` | color→照片/视频 gamma 表，`0xB0` 字节 |
| C | `0xA9B8D0` | 六条曲线，6 × 576 字节 |
| D | `0xA9C650` | 四份转换系数，4 × 64 字节 |
| 消费者跳板 | `0xA9C750` 起 | 八处 look 消费开关扩展 |
| 主名称/属性枚举 | `0xA9CA00` 起 | color19/20 的 FL2/FL3 与 22/23 |
| 第二名称 | `0xA9CAC0` 起 | 原函数 CP `0x23583A` 的扩展分发 |

当前放置方案会将 rodata 映射参数从 `0xD` 改为 `0xF` 以执行洞内跳板，影响整段执行属性；这是一项具体工程取舍，不是任何移植都必须采用的设计。保留原特殊路径、段长度/边界、Thumb 返回位与旧外观行为。

曲线来自 FX2 CP 地址 `0xEBB2BC`、`0xEBB500`、`0xEBBBCC`、`0xEBB744`、`0xEBB988`、`0xEBBE10`。每条取其 580 字节记录的前 572 字节，目标 stride 576，尾部补 4 个零；照片槽 0–5 共享第一条、槽 6 用第二条，视频用槽 6 曲线。

### 本机颜色与设置

在本基线中，`nflasha6` 的 CC1 位于 `0x19CC00`、长度 `0x2000`；block13 位于 `0x1A0C00`、长度 `0x7000`。BIN/BAK 内按 BKID `0x02A40001`、`0x02A4000D` 解析定位，不复制其他相机文件偏移。

- CC1 `0x1236..0x1239` 与 block13 `0x1CC..0x1CF` 写 `[22,24,23,25]`。
- CC1 的 bank22–25 在 `0x1250 + bank × 64`；每项有效系数 24 个 int16 / 48 字节。FX2 `CC1+0xEFE=1` 表示绝对 B/A1/A2，M4 为 0，必须转换为 **B / (A1−B) / (A2−B)**，保留 M4 原格式标志和其他机身校准。
- block13 `0x43E0..0x4FDF` 共 3,072 字节矩阵，从指定 FX2 供体读取。
- 默认 `--matrix-mode fixed-a1`：对 bank22/23/24/25，`base=0x1E0+bank×0x300`，取供体 `[base+0xC0, base+0x180)` 的192字节 A1，写入该 bank 的 B、A1、A2 三段；不将一种外观的 A1 混用于另一种。四个 bank 同时覆盖照片和视频。bank 尾部保留供体导入值，不改变原有机身 WB/校准和其他外观。`--matrix-mode dynamic` 仅用于保留 B/A1/A2 动态端点的研究对照。
- 固定 A1 必须同时存在于活动 nfa6、BACKUP.BIN、BACKUP.BAK；SD 迁移后重新回读，从最新状态局部恢复，不能把旧整区快照直接刷回。
- BIN 与 BAK 各设置六条长度 1、属性 `0x60` 的记录：`02CF12C8=10`、`02CF12CA=11`、`02CF13B0=10`、`02CF13D0=11`、`02CF143E=10`、`02CF1440=11`，分别覆盖 current/still/movie 的槽16/17。
- 对每个 BK4 段检查并更新校验：extent=`u32(+0x18)+u32(+0x1C)`；校验为 byte sum `[0,0x20)` + `[0x24,extent)`，排除四字节校验字段。保留其余记录、文件长度、FAT 分配及分区大小。

## 离线复现

先完成自己的 eMMC **与独立 NOR** 备份，确认目标机实际 AP/CP 与上述原厂哈希一致，再用匹配官方包和供体。下面只构建文件，不刷设备。

```powershell
python -m pip install -e ".[firmware]"
python -m a7m4.firmware decode local/M4-Ver.6.02.DAT --output local/m4-6.02-plain.bin
python -m a7m4.firmware extract-target local/m4-6.02-plain.bin --output local/stock
```

FX2 1.01 用 [fwtool a7iv](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv) 等匹配格式的工具解包（上游入口 `fwtool unpack -f <包> -o <目录>`），取得原始 CP 文件，以及 `0110_backup/SYSIPSX-DSLR/` 下的 BK4 配置模板。按内容哈希确认，不按文件名猜测。提取颜色记录：

```powershell
python -m a7m4.fl23 extract-donor --backup local/fx2/profile.bin --output local/fx2-color
```

输入 `profile.bin` 是解出的实际 BK4 文件的示例名，需替换为你的路径。工具拒绝非指定 FX2 1.01 颜色记录。随后使用**自己相机刚备份**的 nfa2/nfa6：

```powershell
python -m a7m4.fl23 build --ap local/stock/appFw.so --cp local/stock/CPAPP-B.BIN --fx2-cp local/fx2/CPAPP-B.BIN --fx2-cc1 local/fx2-color/cc1.bin --fx2-block13 local/fx2-color/block13.bin --nflasha2 local/my-backup/nflasha2.bin --nflasha6 local/my-backup/nflasha6.bin --matrix-mode fixed-a1 --output output/fl23-components
```

输出 AP、CP、本机 nfa2/nfa6 和哈希清单。可选 `--nflasha8 <本机原厂分区备份>` 同时生成该 FAT 分区镜像。脚本严格校验原程序和供体，拒绝新路径覆盖；不会自行降级你当前的程序。

构建完整 SD 包，指定与你机内更新器相同的密钥。此例明确使用已公开的实验身份，亦可换成自己私有的匹配密钥：

```powershell
python -m a7m4.firmware build-fl23 --official local/M4-Ver.6.02.DAT --components output/fl23-components --public-key keys/published/A7M4_updater_public.pem --private-key keys/published/A7M4_updater_private.pem --version 6.05 --output output/fl23-sd
```

输出 `BODYDATA.DAT` 与 `verification.json`。构建器更新 AP/CP、暖启动标志、更新器信任配置、分区 CRC 清单及头版本/CRC；保留 TAR 布局和其他成员，重算全部 739,727 块校验/重加密/签名/DEND，完整重解码逐字节核对。`work/UNSIGNED_DO_NOT_INSTALL.DAT` 是未签名中间包，禁止安装。SquashFS 重建的时间戳等可能使最终 DAT 哈希随构建变化；AP/CP 的目标哈希固定，不能用历史 DAT 哈希替代当前包自己的核验。

SD 包内部镜像长度可能小于相机完整分区长度，不可直接把解出的 DAT 成员当作 fastboot 整分区镜像。最终包可按 [独立校验命令](../../docs/validation.md) 再核对所有块、签名和六项镜像 CRC。

**这个 SD 包不把你的个人 nfa2/nfa6 写进通用出厂模板，也不自动建立出厂复位后的 FL2/FL3 默认槽。** 其构建完成不表示颜色副本已部署或 NOR 已同步。

## 实机安装顺序

1. 核实基线、可恢复的本机完整 eMMC/boot0/boot1 备份、独立物理 NOR 备份、供电、线序和所有源/目标哈希。确认没有另一台机身连接。
2. 按独立方法 1 建立与最终 DAT 签名公钥匹配的机内更新器。不能依靠包内的新公钥来引导尚不信任它的原厂更新器。
3. 只将刚才基于本机备份生成的 nfa2/nfa6 写回对应分区，完成完整读回核对。熟悉上游 payload 的用户可在已备份的 fastboot 会话使用 `fastboot flash nflasha2 <本机生成镜像>`、`fastboot flash nflasha6 <本机生成镜像>`；这是**外部 fastboot 的直接写入**，不经过主机菜单的备份/确认保护，必须自行先完成备份和核对。不要刷别人的整分区。
4. 重新完整备份到新目录，用新备份的 nfa2/nfa6 与构建输出进行完整 SHA-256 比较；错误时保留 fastboot，使用匹配回滚镜像处理。不要在未核对状态继续 SD 更新。
5. 正常启动后，将最终已验证的 `BODYDATA.DAT` 放在 SD 卡根目录，走与你目标基线匹配的官方 SD 更新流程。满足其电量、机型、版本条件；如果需要调整报告版本，查独立方法 2，并重新核验基线。
6. SD 更新除安装 AP/CP，还通过原有 `nor_loader_writer.sh` / `nor_update` 链将目标 CP 同步至物理 NOR。脚本受 LSI/boot type 条件控制，并可能处理 loader 相关区域。**只通过 fastboot 写 `nflasha8` 不会执行这条链。**
7. 更新后重新备份与回读 eMMC、物理 NOR，检查目标 CP，以及三份颜色字段、BIN/BAK 六键。更新器迁移配置可能改写记录，必要时从新的本机回读重新构建这些字段；不要盲目回刷整个旧设置区。

本仓库 fastboot 备份工具不具备物理 NOR 备份功能。须采用你已审查的独立读出方式并验证 EXBL 布局；缺少这项备份/回读能力时，不应把 eMMC 的“完整备份”当作 NOR 保护。

## NOR 与验收

历史机身通过 EXBL item5 找到 CP 在 NOR 的 `0x200000`，长度 16,236,816；这不是所有读取器/机身都可盲用的固定偏移。该机使用的间接 SPI 读出每个 16 位字需交换相邻字节后再与目标 CP 比较。确认你实际读出工具的字节序和 EXBL 定位后可离线验证：

```powershell
python -m a7m4.fl23 verify-nor --nor local/post-update-nor.bin --cp output/fl23-components/CPAPP-B.BIN --offset 0x200000 --swap16
```

若读出已是规范顺序，省略 `--swap16`。此命令只比较文件，不读取或写入硬件。

分别新拍 FL2、FL3 的 ARW/JPEG，验证拍摄菜单、色彩、回放图标、视频、断电保存及旧外观；新照片 MakerNote 预期 B020 为 FL2/FL3，B029 为 22/23。旧照片的元数据不会自动改变。单独检查恢复出厂、特殊模式和配置迁移。

当前本机6.24的固定 A1 已完成 fastboot 写后及正常开机后完整配置回读；新拍两外观均记录正确名称和编号。FL3 的 RAW 主矩阵105项精确匹配 A1，FL2 为104项，剩余7800右下项1615/1614已定位到WB定点序列化往返。新的无损RAW写出候选通过有界原指令验证，现已在本机6.26安装并以新拍两张原始RAW确认各105项，另提供仅限精确6.24源的配方；未自动合入旧6.02构建。这里公开的默认配置算法已更新，不能把本机6.24安装反馈当成本仓库新构建包的实机验收。详见[当前结果](color-validation-20261017.md)。

**当前结论：FL2/FL3 供体外观数据一致；固定 A1 样片与 Imaging Edge 重选颜色接近，已无此前主要矩阵选择造成的偏色。** 这不等同于 JPEG 零差异，也不等同于复刻 FX2 全部动态插值。若要额外合并电池或镜头方法，分别阅读[方法4](../04-third-party-battery/README.md)、[方法5（未经实机测试）](../05-third-party-lens-af/README.md)；它们不是默认 FL2/FL3 构建的一部分。
