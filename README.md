# Sony A7 IV 自定义固件与工具

> [!WARNING]
> **使用前必读 · 免责声明与使用许可**
>
> 本项目属于非官方独立研究，免费提供固件修改方法、工具和文档，供学习与技术交流。项目与索尼无隶属、授权或背书关系。
>
> **GPLv3 开源许可。** 本项目原创内容自本次许可变更起采用 [GNU GPLv3（GPL-3.0-only）](LICENSE)，允许使用、修改、分享及商业用途，包括商业摄影、软件销售和收费服务。分发适用程序或修改版本时，须按 GPLv3 保留许可与版权声明，并满足对应源代码的提供要求。历史 MIT 内容及第三方组件按各自许可处理。
>
> 作者免费提供本项目，不提供有偿代刷服务，也未授权任何人以作者名义开展收费业务。严禁冒充索尼官方、作者本人或授权服务商，或以这些身份宣传、收费和承诺保修。第三方收费行为由其自行负责。
>
> **开发基线与兼容范围**
>
> **本固件基于中国大陆国行 A7M4 机身及索尼原厂 FE 50mm F1.4 GM 镜头开发。非原厂镜头可能遇到未知的兼容性问题。**
>
> 刷写或修改固件可能导致永久变砖、无法开机、反复重启、功能异常及照片、校准或配置丢失，也可能影响官方更新、保修或维修。接线错误可能损坏相机与电脑。写入成功及读回一致仍需通过实际启动和功能验证，恢复功能也可能无法救回相机。
>
> **任何写入前先备份自己的相机与重要数据。固件更新必须使用索尼原厂电池。** 写入期间保持稳定供电与连接，避免拔线、关机或移除存储卡。USB 插拔按工具明确提示执行。恢复本机应使用本机备份。
>
> **强烈建议在备妥可用的 Fastboot 工具、Multi 接口刷机线及 RP2040-Zero 启动桥后，再进行固件更新**，以便异常时进行维护与恢复。
>
> **建议在 AI Agent 的辅助下进行固件安装。** 大部分常见的安装、驱动和 USB 连接问题，可借助 AI Agent 结合本项目文档、完整报错信息和运行日志进行排查与处理。
>
> **仅操作本人合法持有或已获明确授权的设备。** 请先理解操作流程并完成备份，自行承担设备损坏与维修风险。无法接受这些风险时请退出。

[English](README.en.md) · 中文

**机型与安装基线为 Sony ILCE-7M4（A7 IV / A7M4），安装前固件版本须为索尼官方 V6.02。**

**目前已有国行、港版、日版和加拿大版 A7M4 机身刷入成功的反馈。除国行外，其他地区版本不保证兼容性。**

提供免 Fastboot 安装方法、Fastboot 维护工具与固件功能修改源码。各方法的适用基线以对应文档中的文件哈希为准。

## 一、免 Fastboot 安装固件

使用普通 USB 数据线，通过 **M4 相机工具**准备更新环境，再由相机从 SD 卡安装固件。相机须能正常开机并进入 USB 海量存储模式。

### AI Agent 模式（1.03）

**模型建议：使用 [DeepSeek V4.1 Flash](https://api-docs.deepseek.com/news/news261017/)，或推理、代码与工具调用能力不低于该级别的大模型；Agent 还须具备联网、本机文件访问和命令执行能力。**

把下面整段复制给能够联网、访问本机文件并执行命令的本地 AI Agent。它会下载正式工具、逐步提示操作，也支持单独恢复普通 USB。

```text
请先提醒我：建议使用 DeepSeek V4.1 Flash 或能力相当及以上的大模型，且 Agent 须支持联网、本机文件访问和命令执行。

请完整阅读并遵循项目最新的 Agent 操作说明：
https://github.com/Erlla/sony-a7m4-custom-firmware/blob/main/no-fastboot-install/agent/PROMPT.zh-CN.md

请帮助我操作 Sony A7M4。若我尚未说明目的，先询问本次是“安装固件”还是“仅恢复普通 USB”，然后执行对应流程。

安装固件时，请先询问我是否需要下载最新适用的魔改固件、配套 LUT 包和音频包，等待我选择后再下载。下载后告诉我文件位置和存储卡放置方法；安装完成后按实际固件版本介绍功能用法。

安装准备时，请提示我进入相机 MENU → 设置 → USB → USB连接模式，设为“海量存储器（MSC）”，然后连接电脑，等待我确认设置和连接完成。

全程用简短中文说明当前进度和我需要做什么。实际写入补丁前等待我明确同意；需要系统授权、拔插 USB 或重启时，明确说明具体操作并等待回复。

出现问题时，请主动结合本轮日志、对应构建源码和历史问题排查，修复可验证的主机端问题并复查。确认旧任务已结束且未开始设备操作后，可保留原记录、归档失效状态并生成新的尝试；补丁已经完成时继续后续步骤。记录每次尝试的依据与结果，持续推进到完成或明确的具体阻塞。仅恢复 USB 时使用独立恢复流程。
```

**[Agent 使用入口](no-fastboot-install/agent/README.md)** · [完整操作提示词](no-fastboot-install/agent/PROMPT.zh-CN.md) · [正式运行包](https://github.com/Erlla/sony-a7m4-custom-firmware/releases/tag/A7M4-Agent-ToolKit-V1.03) · [Agent 源码](no-fastboot-install/software/README.md)

### 桌面软件模式（1.03）

1. 将适用的 `BODYDATA.DAT` 放入**卡槽 1 存储卡根目录**。
2. 用普通 USB 数据线连接电脑，在 M4 相机工具中点击**写入补丁**。
3. 等待工具明确提示可以开始更新，再拔下 USB，在相机“版本／软件更新”中安装。

**[安装指南](no-fastboot-install/README.md)** · [软件说明](no-fastboot-install/TOOL-1.0.0.md) · [软件源码与构建](no-fastboot-install/software/README.md) · [原理与修改位置](no-fastboot-install/IMPLEMENTATION.md)

固件安装包、M4 相机工具及 Fastboot 工具包请前往 [Releases](https://github.com/Erlla/sony-a7m4-custom-firmware/releases) 下载。相机工具不校验卡上的固件包，请按安装指南核对文件与操作条件。

## 二、Fastboot 修改方法

Fastboot 路线需要 **Multi 接口刷机线与 RP2040-Zero 启动桥**，普通 USB 数据线不能代替。先完成[接线](docs/wiring.md)、[环境配置](docs/setup.md)与本机备份，再按下表进入对应方法。功能修改源码与安装方式分别说明，组合使用请查看各方法的集成说明。

| 方法 | 功能简介 | 文档 |
|---|---|---|
| SD 更新救砖 | 从 Fastboot 触发机内 SD 卡恢复更新，保留同机设置。 | [使用方法](methods/00-sd-recovery/README.md) |
| 自定义更新签名 | 替换更新公钥、修改公钥验证，支持自签固件包。 | [使用方法](methods/01-custom-signing/README.md) |
| 固件版本显示 | 自行设置相机报告的固件版本号。 | [使用方法](methods/02-firmware-version/README.md) |
| FL2 / FL3 移植 | 移植 FX2 的 FL2、FL3 创意外观及色彩配置，RAW 内置两组备选参数供 Edit 直接重选。 | [使用方法](methods/03-fl2-fl3/README.md) |
| 副厂电池 | 显示电量、取消副厂提示，保留充电与温度保护；更新仍须用原厂电池。 | [使用方法](methods/04-third-party-battery/README.md) |
| 镜头 AF 能力过滤 | 保留镜头上报的兼容能力与速度参数；不承诺对焦提速。 | [使用方法](methods/05-third-party-lens-af/README.md) |
| 自定义声音 | 从 SD 卡导入 WAV，机械／电子快门均可播放；对焦声与快门声相互抢占，最后触发优先，音频和音量分别设置；开机后可能需等待数秒生效。 | [使用方法](methods/06-custom-sounds/README.md) |
| 自定义纵横比 | 新增 17:6、65:24、5:4、7:6、21:9、2.35:1，菜单图标与比例对应；JPEG / HEIF 裁切，RAW 保留原始幅面，普通自动检视保持照片比例。 | [使用方法](methods/07-custom-aspect-ratios/README.md) |
| 自定义 LUT | 从 SD 卡单独导入转换后的 JSON LUT；16 个槽位可随时替换，支持触摸编号栏选择预览，每个滤镜支持 8 项微调与 1 项强度，开机初次使用约 1 秒载入。 | [使用方法](methods/08-custom-lut/README.md) |
| Shell / SSH | 网络 Telnet、USB Shell、SSH / SFTP 与 Multi UART root 终端的开启及集成方法。 | [使用方法](methods/09-shell-access/README.md) |
| 白平衡优化 | 氛围优先 −1、标准 0、白色优先 97，沿用原有 AWB 优先设置。 | [使用方法](methods/10-awb-priority/README.md) |

### 文档导航

| 要做什么 | 入口 |
|---|---|
| 准备刷机线与主机环境 | [接线说明](docs/wiring.md) · [环境与外部资源](docs/setup.md) |
| 备份、恢复与日常维护 | [进阶维护入口](advanced/) · [SD 更新救砖](methods/00-sd-recovery/README.md) |
| 组合功能与迁移安装 | [自定义 LUT 集成](methods/08-custom-lut/INTEGRATION.md) · [FL2 / FL3 的 SD 迁移](methods/03-fl2-fl3/sd-colour-preservation.md) |
| 查看界面与示例文件 | [LUT 界面](methods/08-custom-lut/README.md#实机界面) · [声音与示例音频](examples/custom-sounds/README.md) · [纵横比说明](methods/07-custom-aspect-ratios/README.md) |
| 训练与评估自定义滤镜 | [AI Agent 训练方法](docs/custom-lut-training/AGENT_TRAINING.md) · [当前15款滤镜误差报告](docs/custom-lut-training/README.md) |
| 查阅技术资料 | [色彩对比报告](docs/fl23-colour-comparison-20261018/README.md) · [验证说明](docs/validation.md) · [参考清单](REFERENCES.md) |
| 参与开发 | [贡献指南](CONTRIBUTING.md) · [第三方说明](THIRD_PARTY_NOTICES.md) |

### Fastboot 工具入口

相机端启动文件、RP2040 UF2、对应源码资料及进入／退出／维护／一键救砖脚本见 **[Fastboot 维护工具](fastboot/README.md)**。运行 `python tools/build_fastboot_release.py --output output/A7M4-Fastboot.zip` 可生成独立上传 Release 的压缩包。

**Windows x64 便携版自带 Python、依赖库、Fastboot、SquashFS 工具和 WinUSB 安装器，完整解压后直接运行 BAT。** 新电脑首次安装驱动需管理员授权，并按[驱动说明](fastboot/README.md#便携版)载入 Fastboot 预设。便携版构建器为 `tools/build_fastboot_portable.py`；运行时和工具只进入 Release ZIP。

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

## 三、LUT 训练方法

支持将不同来源的色彩 LUT 或全局调色配方拟合为 A7M4 自定义滤镜。在调色软件中打开提供的索尼大色卡 ARW，应用目标效果，导出原布局的 16 位 sRGB TIFF，再交给 AI Agent 使用 M4 模型训练并输出相机可导入的 JSON。训练在电脑中迭代，复现程度由拟合误差与最终拍摄效果评估。

**[训练入口、代码与素材](training/README.md)** · [AI Agent 执行指南](docs/custom-lut-training/AGENT_TRAINING.md) · [M4 模型说明](training/MODEL.md) · [大色卡与自定义目标](training/DATASETS.md)

模型与大色卡作为独立训练素材附件提供；Sony 参考文件由使用者自行取得。模型复现误差、滤镜匹配误差及实机验收分别记录。[已有训练评估](docs/custom-lut-training/README.md)保留其原始数据范围与时间，不作为新用户的精度保证。

## 声明与许可

本项目为社区研究，与索尼公司无隶属关系。主要补丁基于 **A7M4 官方 6.02**，FL2 / FL3 色彩数据供体为 **FX2 1.01**；具体适用文件见各方法说明。

维护者明确授权发布自己此前使用的 [RSA 密钥对](keys/published/README.md)。**私钥已公开，任何人都能用它签名；使用此公钥的更新器不再能通过签名辨认发布者。** 请自行审核包内容；如需独立信任身份，生成自己的密钥并离线保存私钥。

本仓库公开原创主机源码、补丁配方、说明、指定公开密钥，以及用户授权公开的[三个 WAV 参考音频](examples/custom-sounds/README.md)。索尼固件、供体曲线/矩阵、个人校准、机身备份和外部驱动应由使用者自行取得。第三方内容依其原许可，见 [第三方说明](THIRD_PARTY_NOTICES.md)。启动文件及对应历史源码单独列明[来源与许可范围](fastboot/SOURCES.md)。

本项目原创内容自本次许可变更起采用 **GNU General Public License v3.0 only（GPL-3.0-only）**。允许商业和非商业使用、修改及分发。分发适用程序或其修改版本时，应按 GPLv3 保留版权及许可声明、标明修改，并满足对应源代码的提供要求。具体权利、义务及免责条款以英文协议原文为准。[完整许可](LICENSE)

截至提交 `468043977f9ca5fd0bf03b2002f6e40f35cbf667` 已按 MIT 发布的代码、文档及贡献继续享有原许可授予的权利，包括商业使用权。后续新增原创内容及修改按 GPLv3 授权。[历史 MIT 许可](LICENSE-MIT-LEGACY)


## 致谢

感谢以下项目公开研究成果，为本项目提供参考：

| 项目 | 参考内容 |
|---|---|
| [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools) | 免 Fastboot 安装方案的研究与实现思路。 |
| [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) | 串行启动、RP2040 桥、Fastboot payload 与 eMMC 访问。 |
| [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) | FL2 / FL3 参数与安装研究。 |
| [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) | 原生色彩参数、网格生命周期、LUT 拟合思路与合成大色卡参考；特别感谢项目作者 **Hearts-Ace 对训练方法的大力支持**。 |
| [751K/sony-look-bridge](https://github.com/751K/sony-look-bridge) | Sony Edit 的 RAW 显影算子与创意外观矩阵/Gamma 实现，为 M4 电脑模型的原生处理前段提供运算基础。 |
| [DavidBuchanan314/fwtool.py](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv) 与 [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | 固件容器格式与解包方法。 |
| [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) | 索尼相机协议与固件研究。 |
| [q19032/Sony-firmware-unpacker](https://github.com/q19032/Sony-firmware-unpacker) | 固件解密与密钥推导研究。 |
| [DavidBuchanan314/Sony-ILCE-7M4-Linux](https://github.com/DavidBuchanan314/Sony-ILCE-7M4-Linux) | 平台 Linux 参考源码。 |

同时感谢所使用的开源工具与依赖。完整归属、用途及许可见[参考清单](REFERENCES.md)与[第三方说明](THIRD_PARTY_NOTICES.md)。

## 参与贡献

欢迎通过 Issue 或 Pull Request 提交问题与改进。新增基线请附输入哈希、地址映射与修改依据；请勿提交个人私钥、机身校准、备份或完整固件。详见[贡献指南](CONTRIBUTING.md)。

