# Sony A7 IV 自定义固件与工具

> **刷机风险声明**
>
> 刷写或修改固件可能导致永久变砖、无法开机、校准或配置丢失；接线错误可能损坏相机与电脑。请自行承担操作风险。
>
> **任何写入前先备份自己的相机；固件更新必须使用索尼原厂电池。** 写入期间保持稳定供电与连接，不拔线、不关机，不使用其他机身的备份恢复本机。

[English](README.en.md) · 中文

**适用版本：Sony ILCE-7M4（A7 IV / A7M4）官方 V6.02 固件。**

提供免 Fastboot 安装方法、Fastboot 维护工具与固件功能修改源码。各方法的适用基线以对应文档中的文件哈希为准。

## 一、免 Fastboot 安装固件

使用普通 USB 数据线，通过 **M4 相机工具**准备更新环境，再由相机从 SD 卡安装固件。相机须能正常开机并进入 USB 海量存储模式。

1. 将适用的 `BODYDATA.DAT` 放入**卡槽 1 存储卡根目录**。
2. 用普通 USB 数据线连接电脑，在 M4 相机工具中点击**写入补丁**。
3. 等待工具明确提示可以开始更新，再拔下 USB，在相机“版本／软件更新”中安装。

**[安装指南](no-fastboot-install/README.md)** · [软件说明](no-fastboot-install/TOOL-1.00.md) · [软件源码与构建](no-fastboot-install/software/README.md) · [原理与修改位置](no-fastboot-install/IMPLEMENTATION.md)

**当前暂不提供完整固件，待全部功能更新完毕后再提供。** 软件不附带或校验固件包，请按安装指南核对文件与操作条件。

## 二、Fastboot 修改方法

Fastboot 路线需要 **Multi 接口刷机线与 RP2040-Zero 启动桥**，普通 USB 数据线不能代替。先完成[接线](docs/wiring.md)、[环境配置](docs/setup.md)与本机备份，再按下表进入对应方法。功能修改源码与安装方式分别说明，组合使用请查看各方法的集成说明。

| 方法 | 功能简介 | 文档 |
|---|---|---|
| SD 更新救砖 | 从 Fastboot 触发机内 SD 卡恢复更新，保留同机设置。 | [使用方法](methods/00-sd-recovery/README.md) |
| 自定义更新签名 | 替换更新公钥、修改公钥验证，支持自签固件包。 | [使用方法](methods/01-custom-signing/README.md) |
| 固件版本显示 | 自行设置相机报告的固件版本号。 | [使用方法](methods/02-firmware-version/README.md) |
| FL2 / FL3 移植 | 移植 FX2 的 FL2、FL3 创意外观及相关色彩配置。 | [使用方法](methods/03-fl2-fl3/README.md) |
| 副厂电池 | 显示电量、取消副厂提示，保留充电与温度保护；更新仍须用原厂电池。 | [使用方法](methods/04-third-party-battery/README.md) |
| 镜头 AF 能力过滤 | 保留镜头上报的兼容能力与速度参数；不承诺对焦提速。 | [使用方法](methods/05-third-party-lens-af/README.md) |
| 自定义声音 | 从 SD 卡导入 WAV，机械／电子快门均可播放自定义声音，对焦声与音量分别设置。 | [使用方法](methods/06-custom-sounds/README.md) |
| 自定义纵横比 | 新增 17:6、65:24、5:4、7:6；JPEG / HEIF 裁切，RAW 保留原始幅面。 | [使用方法](methods/07-custom-aspect-ratios/README.md) |
| 自定义 LUT | 从 SD 卡单独导入转换后的 JSON LUT；16 个槽位可随时替换，每个滤镜支持 8 项微调与 1 项强度，开机初次使用约 1 秒载入。 | [使用方法](methods/08-custom-lut/README.md) |

### 文档导航

| 要做什么 | 入口 |
|---|---|
| 准备刷机线与主机环境 | [接线说明](docs/wiring.md) · [环境与外部资源](docs/setup.md) |
| 备份、恢复与日常维护 | [进阶维护入口](advanced/) · [SD 更新救砖](methods/00-sd-recovery/README.md) |
| 组合功能与迁移安装 | [自定义 LUT 集成](methods/08-custom-lut/INTEGRATION.md) · [FL2 / FL3 的 SD 迁移](methods/03-fl2-fl3/sd-colour-preservation.md) |
| 查看界面与示例文件 | [LUT 界面](methods/08-custom-lut/README.md#实机界面) · [声音与示例音频](examples/custom-sounds/README.md) · [纵横比说明](methods/07-custom-aspect-ratios/README.md) |
| 查阅技术资料 | [色彩对比报告](docs/fl23-colour-comparison-20261018/README.md) · [验证说明](docs/validation.md) · [参考清单](REFERENCES.md) |
| 参与开发 | [贡献指南](CONTRIBUTING.md) · [第三方说明](THIRD_PARTY_NOTICES.md) |

### Fastboot 工具入口

支持完整备份、版本查看与设置、自签更新器构建、同机备份恢复和恢复官方验签。环境要求：**Windows 10 / 11、Python 3.11+**。

克隆仓库后，运行 `setup.bat` 安装依赖，再运行 `advanced/进阶维护菜单.bat`。外部工具与驱动按[环境说明](docs/setup.md)准备。

<details>
<summary>命令行安装与启动</summary>

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
# 纯模拟，不操作相机
.\.venv\Scripts\python.exe -m a7m4 --demo maintain
# 检查本地资源
.\.venv\Scripts\python.exe -m a7m4 doctor
# 实机维护：先进入 Fastboot 并完整备份
.\.venv\Scripts\python.exe -m a7m4 maintain
```

已进入 Fastboot 时可用 `maintain --already-fastboot`，仍需完成备份与写入计划确认。

</details>

<details>
<summary>备份范围与恢复条件</summary>

- 保存本机全部 eMMC 分区、boot0 / boot1、分区表和 SHA-256，另存离线副本；涉及 FL2 / FL3 时另行备份物理 CP NOR。
- 常规维护要求本次连接的完整 eMMC 分区备份，写后完整读回校验。范围为 payload 提供的分区，不包括独立 CP NOR、其他 MCU 或全部硬件状态。
- 救砖入口的六分区备份、免 Fastboot 工具的 p1 备份均不等于完整 eMMC / NOR 备份。SD 救砖要求已进入 Fastboot 且更新器匹配支持的布局。
- 备份不保证所有故障均可恢复。固定地址补丁只能用于对应基线，不能按相近版本号套用。

</details>

## 声明与许可

本项目为社区研究，与索尼公司无隶属关系。主要补丁基于 **A7M4 官方 6.02**，FL2 / FL3 色彩数据供体为 **FX2 1.01**；具体适用文件见各方法说明。

维护者明确授权发布自己此前使用的 [RSA 密钥对](keys/published/README.md)。**私钥已公开，任何人都能用它签名；使用此公钥的更新器不再能通过签名辨认发布者。** 请自行审核包内容；如需独立信任身份，生成自己的密钥并离线保存私钥。

本仓库公开原创主机源码、补丁配方、说明、指定公开密钥，以及用户授权公开的[三个 WAV 参考音频](examples/custom-sounds/README.md)。索尼固件、供体曲线/矩阵、个人校准、机身备份和外部驱动应由使用者自行取得。源码采用 [MIT](LICENSE)，第三方内容依其原许可，见 [第三方说明](THIRD_PARTY_NOTICES.md)。上游部分公开研究仓库没有明确再分发许可，因此这里只链接来源，不把其 payload 重新打包为本项目的 MIT 软件。


## 致谢

感谢以下项目公开研究成果，为本项目提供参考：

| 项目 | 参考内容 |
|---|---|
| [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools) | 免 Fastboot 安装方案的研究与实现思路。 |
| [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) | 串行启动、RP2040 桥、Fastboot payload 与 eMMC 访问。 |
| [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) | FL2 / FL3 参数与安装研究。 |
| [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) | 原生色彩参数、网格生命周期研究，以及 R5ColorLab 的 LUT 拟合思路。 |
| [DavidBuchanan314/fwtool.py](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv) 与 [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | 固件容器格式与解包方法。 |
| [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) | 索尼相机协议与固件研究。 |
| [q19032/Sony-firmware-unpacker](https://github.com/q19032/Sony-firmware-unpacker) | 固件解密与密钥推导研究。 |
| [DavidBuchanan314/Sony-ILCE-7M4-Linux](https://github.com/DavidBuchanan314/Sony-ILCE-7M4-Linux) | 平台 Linux 参考源码。 |

同时感谢所使用的开源工具与依赖。完整归属、用途及许可见[参考清单](REFERENCES.md)与[第三方说明](THIRD_PARTY_NOTICES.md)。

## 参与贡献

欢迎通过 Issue 或 Pull Request 提交问题与改进。新增基线请附输入哈希、地址映射与修改依据；请勿提交个人私钥、机身校准、备份或完整固件。详见[贡献指南](CONTRIBUTING.md)。
