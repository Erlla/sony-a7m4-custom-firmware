# Sony A7 IV 自定义固件、Fastboot 工具与研究方法

[English](README.en.md) · 中文

针对 **Sony ILCE-7M4（A7 IV / A7M4）** 的社区研究。提供精简的 Windows fastboot 主机工具、可审查的源码和五份独立方法。与索尼公司无隶属关系。主要补丁源于 **A7M4 官方 6.02**；FL2/FL3 供体为 **FX2 1.01**。各方法按文件哈希严格识别支持基线；镜头方法另列历史实验6.13 CP。实验固件版本号不代表索尼官方版本。

## 先读风险与备份要求

**刷机可能造成永久变砖、无法开机、校准或配置丢失，接线错误还可能损坏相机和电脑。你需要自行承担风险。不要把本项目用于无法承担损失的设备。** 有效签名、脚本运行成功或菜单出现，都不等于刷写安全或功能完整。

- **任何刷写前必须备份自己的相机**：保存全部 eMMC 分区、boot0/boot1、分区表和 SHA-256，至少另存一份离线副本。涉及 FL2/FL3 时，还要独立备份物理 CP NOR。保留原厂升级包、工具版本、改动清单与回滚镜像。
- 主机工具强制验证本次连接的完整 eMMC 分区备份，才允许维护写入；写后进行完整分区读回 SHA-256 校验。备份覆盖 payload 列出的分区，并非整颗芯片所有地址。**它不包含独立 CP NOR、其他 MCU 或所有硬件状态**，也不保证任何故障都可恢复。
- 保持可靠供电与 USB 连接，不在写入时拔线、断电或强制退出。不要用另一台相机的完整设置、校准或 eMMC 镜像恢复你的机身。
- **刷机需要一条自制刷机线**：相机 Multi 接口引出线 + RP2040-Zero 启动桥 + 共地与正确的电平接口；普通 USB 数据线不能代替。请先读 [接线说明](docs/wiring.md)。相机 Multi 串行信号电平约 **3.15 V**，RP2040 为 3.3 V 器件；按接线说明使用开漏模式并核对信号上拉与 RESET 接法。
- 不支持把本机固定地址补丁直接套用到其他机型或固件版本；版本号相近也不表示二进制兼容。

## 五个独立方法

| 方法 | 单独入口 | 本仓库提供的内容 |
|---|---|---|
| 1. 取代官方更新公钥，并修改公钥真实性验证 | [中文](methods/01-custom-signing/README.md) / [English](methods/01-custom-signing/README.en.md) | 从本机更新器镜像替换 PEM，校验四库原函数后修改 `verifyKey`，重建 SquashFS/校验和；发布维护者原有密钥对和 DAT 重新签名工具 |
| 2. 自行设置报告的固件版本 | [中文](methods/02-firmware-version/README.md) / [English](methods/02-firmware-version/README.en.md) | 解析本机 FAT，修改 `updater/dat4` 的两字节 BCD，支持 `0.00`–`9.99`，保留其余内容 |
| 3. FL2 / FL3 移植与刷入 | [中文](methods/03-fl2-fl3/README.md) / [English](methods/03-fl2-fl3/README.en.md) | AP/CP、供体数据转换、配置及 NOR 同步；**固定 A1 已有实拍对照，颜色接近软件重选目标** |
| 4. 副厂电池电量显示与提示限制 | [中文](methods/04-third-party-battery/README.md) / [English](methods/04-third-party-battery/README.en.md) | 16条 AP 指令恢复真实电量显示、跳过副厂提示，保留认证源状态与充电/温度保护；附精确配方、离线补丁与回滚 |
| 5. 镜头 AF 机制与兼容能力过滤 | [中文](methods/05-third-party-lens-af/README.md) / [English](methods/05-third-party-lens-af/README.en.md) | 分别分析 ID 能力过滤与类别/能力/档案范围门控；六处 CP 补丁仅保留上报能力和速度 profile，范围门控未修改；**速度改善未经实机测试** |

方法 1 不会自动安装 FL2/FL3；方法 2 修改的是报告版本，不能自动使旧程序具备新功能。方法 3 的安装前提与完整流程在自己的文档中说明。

**FL2/FL3 外观数据与 FX2 供体一致，默认固定 A1，实拍与 Imaging Edge 重选颜色接近；不宣称像素完全相同或 FX2 全场景等效。副厂镜头对焦速度限制修改尚未经过实机测试，效果未知。** 方法4、5独立提供原理、基线、补丁和验证边界；SD 构建只有显式传入 `--battery` / `--lens-af` 才合并对应功能。

当前维护者6.26的新拍原始RAW，FL2/FL3各105项主矩阵均匹配FX2 A1，FL2一单位写出误差已修复。[验收与精确源补丁](methods/03-fl2-fl3/README.md)。公开6.02构建默认固定A1；独立RAW配方只接受文档指定的实验6.24完整CP，不会自动合入旧构建。

## Fastboot 工具

保留完整备份、版本查看/设置、自签更新器构建、同机备份恢复和恢复官方验签。`advanced/` 提供中文 BAT 入口。**不包含交互串口控制台、串口命令行、任意 UART 命令或串口更新模式切换。** RP2040 的串行启动传输仍是进入 fastboot 必需的硬件协议，不是相机控制台功能。

Windows 10/11、Python 3.11+。克隆仓库后：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

按 [环境与外部资源](docs/setup.md) 准备 fastboot、RP2040 UF2、相机启动 payload、驱动和 SquashFS 工具。仓库不捆绑这些外部二进制，不提供索尼完整固件或机身备份。

```powershell
# 纯模拟，无相机、驱动或串口操作
.\.venv\Scripts\python.exe -m a7m4 --demo maintain
# 检查本地资源，不操作设备
.\.venv\Scripts\python.exe -m a7m4 doctor
# 实机入口：先进入 fastboot 并完整备份，再显示维护菜单
.\.venv\Scripts\python.exe -m a7m4 maintain
```

也可运行 `setup.bat` 安装 Python 依赖，然后运行 `advanced/进阶维护菜单.bat`。每个写入操作都会显示分区、原/目标哈希和与该计划绑定的完整确认文字。已在 fastboot 的用户可用 `maintain --already-fastboot`；完整备份要求仍然有效。

## 公开密钥与发布边界

维护者明确授权发布自己此前使用的 [RSA 密钥对](keys/published/README.md)。**私钥已公开，任何人都能用它签名；使用此公钥的更新器不再能通过签名辨认发布者。** 请自行审核包内容；如需独立信任身份，生成自己的密钥并离线保存私钥。

本仓库公开原创主机源码、补丁配方、说明和指定实验密钥。索尼固件、供体曲线/矩阵、个人校准、机身备份和外部驱动应由使用者自行取得。源码采用 [MIT](LICENSE)，第三方内容依其原许可，见 [第三方说明](THIRD_PARTY_NOTICES.md)。上游部分公开研究仓库没有明确再分发许可，因此这里只链接来源，不把其 payload 重新打包为本项目的 MIT 软件。

## 参考项目与致谢

本次公开内容直接使用或参考的项目如下；具体用途、来源修订和运行依赖/研究工具的区别见 [完整参考清单](REFERENCES.md)。

- [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE)：串行启动、RP2040 桥、相机 fastboot payload、eMMC 访问。
- [DavidBuchanan314/fwtool.py，a7iv 分支](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv) 与 [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py)：升级包格式、解包与研究。
- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE)：索尼相机协议与固件研究背景。
- [ExifTool](https://exiftool.org/) 的 [Sony LensType2 表](https://exiftool.org/TagNames/Sony.html)：镜头 ID 类别的研究参考，不代替实际镜头采样。
- [q19032/Sony-firmware-unpacker](https://github.com/q19032/Sony-firmware-unpacker)：固件解密与密钥推导研究参考。
- [DavidBuchanan314/Sony-ILCE-7M4-Linux](https://github.com/DavidBuchanan314/Sony-ILCE-7M4-Linux)：平台 Linux 参考源码。
- [AOSP fastboot](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/) 与 [squashfs-tools-ng](https://github.com/AgentD/squashfs-tools-ng)：主机 USB 工具与更新器文件系统重建。
- [arduino-pico](https://github.com/earlephilhower/arduino-pico)、[Pico SDK](https://github.com/raspberrypi/pico-sdk)：RP2040 构建依赖。
- [pySerial](https://github.com/pyserial/pyserial)、[pyelftools](https://github.com/eliben/pyelftools)、[cryptography](https://github.com/pyca/cryptography)：主机运行依赖。
- [Dissect](https://github.com/fox-it/dissect)、[PyCryptodome](https://github.com/Legrandin/pycryptodome)、[Capstone](https://github.com/capstone-engine/capstone)、[Unicorn](https://github.com/unicorn-engine/unicorn)、[Keystone](https://github.com/keystone-engine/keystone)：离线文件系统、封装、反汇编、指令重放与补丁研究。
- [Python](https://github.com/python/cpython)、[pytest](https://github.com/pytest-dev/pytest)、[setuptools](https://github.com/pypa/setuptools)：语言、测试与打包工具。
- [NumPy](https://github.com/numpy/numpy)、[Dissect extfs](https://github.com/fox-it/dissect.extfs)、[util](https://github.com/fox-it/dissect.util)、[cstruct](https://github.com/fox-it/dissect.cstruct)：可选完整固件构建依赖。
- [Arduino CLI](https://github.com/arduino/arduino-cli)、[GCC](https://gcc.gnu.org/)、[GNU Binutils](https://www.gnu.org/software/binutils/)：外部桥/payload 构建工具；[OpenSSL](https://github.com/openssl/openssl)、[cffi](https://github.com/python-cffi/cffi)、[pycparser](https://github.com/eliben/pycparser)、[pip](https://github.com/pypa/pip)：加密与安装链依赖。

## 验证与贡献

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python tools/check_public_tree.py
```

测试使用合成数据，不会连接相机。历史实机反馈、当前离线复现和未验证项在各方法及 [验证说明](docs/validation.md) 中分别列出。精简后的工具尚未完成一次新的实机刷写验收。贡献新基线时请提交地址映射、输入哈希、差分和验证依据；不要提交他人的私钥、机身数据或完整固件。
