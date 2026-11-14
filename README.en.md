# Sony A7 IV custom firmware and tools

> [!WARNING]
> **Read before use · Disclaimer and license**
>
> This independent community research project provides firmware modification methods, tools and documentation free of charge for learning and technical exchange. Sony has no affiliation with, authorization of or endorsement of this project.
>
> **GPLv3 open-source license.** Original project material released from this license change uses [GNU GPLv3 (GPL-3.0-only)](LICENSE), permitting use, modification, sharing and commercial activities, including commercial photography, software sales and paid services. Distribution of covered programs or modified versions must preserve license and copyright notices and meet the GPLv3 requirements for providing Corresponding Source. Historical MIT material and third-party components follow their respective licenses.
>
> The author provides this project free of charge, offers no paid flashing service and has authorized no one to offer paid services in the author's name. Impersonating Sony, the author or an authorized provider, including claims of warranty coverage under those identities, is prohibited. Third parties are responsible for their own paid activities.
>
> **Development baseline and compatibility**
>
> **This firmware was developed using a mainland-China-market A7M4 camera and an original Sony FE 50mm F1.4 GM lens. Third-party lenses may encounter unknown compatibility issues.**
>
> Writing or modifying firmware can permanently brick the camera, prevent booting, cause boot loops or malfunctions, and destroy photographs, calibration or settings. Official updates, warranty coverage and repairs may also be affected. Incorrect wiring can damage the camera and computer. Successful writes and matching readbacks still require actual boot and functional validation. Recovery functions can also fail to restore the camera.
>
> **Back up your own camera and important data before any write. Use an original Sony battery for firmware updates.** Maintain stable power and connections throughout writes, and avoid unplugging, powering off or removing the card. Follow explicit tool prompts for USB reconnection. Restore your camera using its own backup.
>
> **We strongly recommend having working Fastboot tools, a Multi-port flashing cable and an RP2040-Zero boot bridge ready before updating firmware**, so maintenance and recovery are available if something goes wrong.
>
> **We recommend installing the firmware with assistance from an AI Agent.** For most common installation, driver and USB connection issues, an AI Agent can help investigate and address the problem using the project documentation, complete error messages and runtime logs.
>
> **Operate only equipment you lawfully own or have explicit permission to modify.** Understand the procedure and complete backups first. You bear the risks of device damage and repair costs. Stop if you cannot accept those risks.

English · [中文](README.md)

**The installation baseline is a Sony ILCE-7M4 (A7 IV / A7M4) running official Sony firmware V6.02 before installation.**

**Successful flashing has been reported on mainland China, Hong Kong, Japan and Canada-market A7M4 cameras. Compatibility is not guaranteed for regional variants other than mainland China.**

Provides installation without Fastboot, Fastboot maintenance tools and source for firmware modifications. Supported input hashes are documented in each method guide.

## 1. Install firmware without Fastboot

Use a normal USB data cable and **M4 Camera Tool** to prepare the updater, then install firmware from the camera SD card. The camera must boot normally and enter USB mass-storage mode.

### AI Agent mode (1.03)

**We recommend DeepSeek V4.1 Flash or a model with comparable or stronger reasoning, coding and tool-use capabilities. The Agent also needs internet access, local file access and command execution.** [DeepSeek V4.1 Flash](https://api-docs.deepseek.com/news/news261017/)

Copy the entire prompt below into a local AI Agent with those capabilities. It will download the official tool package and guide you through the steps. It also supports restoring normal USB connectivity on its own.

```text
First, remind me that DeepSeek V4.1 Flash or a model with comparable or stronger capabilities is recommended, and that the Agent needs internet access, local file access and command execution.

Read and follow the project's latest Agent operating instructions in full. The instructions are written in Chinese. Communicate with me in English throughout this task.
https://github.com/Erlla/sony-a7m4-custom-firmware/blob/main/no-fastboot-install/agent/PROMPT.zh-CN.md

Help me operate my Sony A7M4. If I have not stated my goal, first ask whether I want to install firmware or only restore normal USB connectivity, then follow the appropriate workflow.

For firmware installation, first ask whether I want to download the latest compatible custom firmware, matching LUT pack and audio pack. Wait for my selection before downloading. After downloading, tell me where the files are and how to place them on the memory card. After installation, explain how to use the features available in the firmware version actually installed.

During installation preparation, ask me to open the camera's MENU → Setup → USB → USB Connection Mode, select Mass Storage (MSC), and then connect the camera to the computer. Wait for me to confirm that the setting and connection are ready.

Use concise English to explain progress and what I need to do. Wait for my explicit approval before writing the patch. When system authorization, USB reconnection or a restart is needed, explain the exact action and wait for my reply.

If a problem occurs, actively investigate using this session's logs, the source matching the tool build and previous issues. Fix verifiable host-side problems and check the result. After confirming that the old task has ended and device operations have not started, preserve its records, archive stale state and create a new attempt as appropriate. If patching is already complete, continue with the remaining steps. Record the basis and result of each attempt, and keep working until completion or a specific blocker is identified. For USB-only recovery, use the independent recovery workflow.
```

**[Agent getting started (Chinese)](no-fastboot-install/agent/README.md)** · [Full operating instructions (Chinese)](no-fastboot-install/agent/PROMPT.zh-CN.md) · [Official runtime package](https://github.com/Erlla/sony-a7m4-custom-firmware/releases/tag/A7M4-Agent-ToolKit-V1.03) · [Agent source](no-fastboot-install/software/README.en.md)

### Desktop application mode (1.03)

1. Place a compatible `BODYDATA.DAT` in the **root of the card in slot 1**.
2. Connect the camera to the computer with a normal USB cable and select **写入补丁 (Write patch)** in M4 Camera Tool.
3. Wait for the tool to explicitly allow updating, disconnect USB, then install through the camera's version / software-update menu.

**[Installation guide](no-fastboot-install/README.en.md)** · [Software guide](no-fastboot-install/TOOL-1.0.0.md) · [Source and build](no-fastboot-install/software/README.en.md) · [Principle and patch locations](no-fastboot-install/IMPLEMENTATION.md)

Download firmware packages, M4 Camera Tool and the Fastboot toolkit from [Releases](https://github.com/Erlla/sony-a7m4-custom-firmware/releases). The camera tool does not validate the firmware package on the card; follow the installation guide to check files and prerequisites.

## 2. Fastboot modification methods

The Fastboot route requires a **Multi-port flashing cable and an RP2040-Zero boot bridge**; a normal USB cable is insufficient. Complete [wiring](docs/wiring.en.md), [setup](docs/setup.en.md) and your camera's backup before using a method below. Feature source and installation routes are documented separately; consult each method's integration notes when combining features.

| Method | Function | Guide |
|---|---|---|
| SD update recovery | Trigger the camera's SD recovery updater from Fastboot while preserving same-body settings. | [Instructions](methods/00-sd-recovery/README.en.md) |
| Custom update signing | Replace the update key and modify key verification to support self-signed packages. | [Instructions](methods/01-custom-signing/README.en.md) |
| Firmware version display | Set the firmware version reported by the camera. | [Instructions](methods/02-firmware-version/README.en.md) |
| FL2 / FL3 port | Port FX2 FL2/FL3 Creative Looks and colour configuration, and embed two alternative parameter sets in RAW files for direct selection in Edit. | [Instructions](methods/03-fl2-fl3/README.en.md) |
| Third-party batteries | Show battery percentage and suppress the caution while retaining charging and temperature protection. Updates still require a Sony battery. | [Instructions](methods/04-third-party-battery/README.en.md) |
| Lens AF capability filtering | Retain lens-reported capabilities and speed profiles; no focus-speed improvement is promised. | [Instructions](methods/05-third-party-lens-af/README.en.md) |
| Custom sounds | Import WAVs from SD for mechanical/electronic shutters; focus and shutter sounds preempt each other, with the latest trigger taking priority and separate clips and volumes. May take a few seconds to activate after power-on. | [Instructions](methods/06-custom-sounds/README.en.md) |
| Custom aspect ratios | Add 17:6, 65:24, 5:4, 7:6, 21:9 and 2.35:1 with matching menu icons and JPEG / HEIF cropping; preserve RAW area and photo proportions in normal automatic review. | [Instructions](methods/07-custom-aspect-ratios/README.en.md) |
| Custom LUTs | Import converted JSON LUTs individually from SD; 16 replaceable slots with touch selection from the number column, eight adjustments plus strength per filter, and approximately one-second loading on first use after power-on. | [Instructions](methods/08-custom-lut/README.en.md) |
| Shell / SSH | Activation and integration of network Telnet, USB shell, SSH / SFTP and Multi UART root terminals. | [Instructions](methods/09-shell-access/README.en.md) |
| White-balance tuning | Set Ambience to −1, retain Standard at 0, and set White priority to 97 using the existing AWB settings. | [Instructions](methods/10-awb-priority/README.en.md) |

### Documentation navigation

| Task | Links |
|---|---|
| Prepare hardware and the host | [Wiring](docs/wiring.en.md) · [Setup and external resources](docs/setup.en.md) |
| Back up, restore and maintain | [Advanced maintenance](advanced/) · [SD update recovery](methods/00-sd-recovery/README.en.md) |
| Combine features and migrate installs | [Custom LUT integration](methods/08-custom-lut/INTEGRATION.md) · [FL2 / FL3 SD migration](methods/03-fl2-fl3/sd-colour-preservation.md) |
| View interfaces and sample files | [LUT interface](methods/08-custom-lut/README.en.md#camera-photographs) · [Sound samples](examples/custom-sounds/README.en.md) · [Aspect ratios](methods/07-custom-aspect-ratios/README.en.md) |
| Train and evaluate custom looks | [AI Agent training method](docs/custom-lut-training/AGENT_TRAINING.en.md) · [Current 15-look error report](docs/custom-lut-training/README.en.md) |
| Read technical references | [Colour comparison](docs/fl23-colour-comparison-20261018/README.md) · [Validation notes](docs/validation.md) · [Reference register](REFERENCES.md) |
| Contribute | [Contribution guide](CONTRIBUTING.md) · [Third-party notices](THIRD_PARTY_NOTICES.md) |

### Fastboot tools

The **[Fastboot toolkit](fastboot/README.md)** includes the camera boot assets, RP2040 UF2, corresponding source material, and scripts for entering and exiting Fastboot, maintenance and SD recovery. Run `python tools/build_fastboot_release.py --output output/A7M4-Fastboot.zip` to generate a standalone archive for upload to Releases.

**The Windows x64 portable archive includes Python, its dependencies, Fastboot, SquashFS tools and a WinUSB installer. Extract it completely and run the BAT entries.** First-time driver installation on a new computer requires administrator approval. Load the Fastboot preset as described in the driver instructions. The portable builder is `tools/build_fastboot_portable.py`, and runtime binaries and tools are distributed in the Release ZIP. [Driver instructions (Chinese)](fastboot/README.md#便携版)

Includes complete backups, version inspection and editing, custom updater preparation, same-camera restoration and restoration of official verification. Requires **Windows 10 / 11 and Python 3.11+**.

After cloning, run `setup.bat` to install dependencies, then `advanced/进阶维护菜单.bat`. Prepare external tools and drivers using the [setup guide](docs/setup.en.md).

<details>
<summary>Command-line installation and launch</summary>

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
# Simulation only: no camera operations
.\.venv\Scripts\python.exe -m a7m4 --demo maintain
# Check local resources
.\.venv\Scripts\python.exe -m a7m4 doctor
# Hardware maintenance: enter Fastboot and complete a full backup first
.\.venv\Scripts\python.exe -m a7m4 maintain
```

Use `maintain --already-fastboot` if already connected in Fastboot. Backup and write-plan confirmation remain required.

</details>

<details>
<summary>Backup scope and recovery requirements</summary>

- Preserve all eMMC partitions, boot0 / boot1, the partition table and SHA-256 hashes, with an offline copy. Back up physical CP NOR separately for FL2 / FL3 work.
- Normal maintenance requires a complete backup of the eMMC partitions exposed by the payload from the current connection and full readback verification after writing. Separate CP NOR, other MCUs and some hardware state are excluded.
- Recovery's six-partition backup and the no-Fastboot tool's p1 backup are not complete eMMC / NOR backups. SD recovery requires an existing Fastboot connection and a supported updater layout.
- Backups cannot guarantee recovery from every failure. Fixed-offset patches apply only to their documented inputs, regardless of similar displayed version numbers.

</details>

## 3. LUT training methods

Fit colour LUTs from different sources or global grading recipes into A7M4 custom looks. Open the supplied Sony chart ARW in a grading application, apply the desired look, export a 16-bit sRGB TIFF with the original chart layout, and give it to an AI Agent to fit with the M4 model and produce camera-importable JSON. Iterations run on the computer. Fitting errors and final photographs establish the degree of reproduction.

**[Training source and assets](training/README.en.md)** · [Agent execution guide](docs/custom-lut-training/AGENT_TRAINING.en.md) · [M4 model](training/MODEL.en.md) · [Dense chart and targets](training/DATASETS.en.md)

Models/charts are separate training assets; users obtain Sony reference files independently. Model agreement, style error and physical acceptance remain separate. [Existing evaluations](docs/custom-lut-training/README.en.md) retain their original scope/date and are not new-user accuracy guarantees.

## Disclaimer and licensing

This community project is not affiliated with Sony. Most recipes derive from **official A7M4 6.02**, with **FX2 1.01** as the FL2 / FL3 colour-data donor. See each method for its supported inputs.

The maintainer explicitly authorized publication of their previously used RSA key pair. **The private key is public. Anyone can sign with it, so an updater using this public key cannot authenticate the publisher through signatures.** Review package contents yourself. For an independent signing identity, generate your own key pair and keep the private key offline. [Published RSA key pair](keys/published/README.md)

This repository publishes original host code, patch recipes, documentation, the specified public keys and [three user-authorized WAV samples](examples/custom-sounds/README.en.md). Obtain Sony firmware, donor curves/matrices, camera calibration, backups and external drivers separately. Third-party material follows its own terms, described in [third-party notices](THIRD_PARTY_NOTICES.md). Boot assets and historical source material have separate [source and licensing notes](fastboot/SOURCES.md).

Original project material released from this license change uses the **GNU General Public License v3.0 only (GPL-3.0-only)**. Commercial and noncommercial use, modification and distribution are permitted. Distribution of covered programs or modified versions must preserve copyright and license notices, identify changes and meet the GPLv3 requirements for providing Corresponding Source. The original English license text defines the rights, obligations and disclaimers. [Full license](LICENSE)

Code, documentation and contributions already published under MIT through commit `468043977f9ca5fd0bf03b2002f6e40f35cbf667` retain their original grants, including commercial-use rights. Subsequent original material and changes are licensed under GPLv3. [Historical MIT license](LICENSE-MIT-LEGACY)


## Acknowledgements

Thanks to the following projects for sharing the research referenced here:

| Project | Reference |
|---|---|
| [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools) | Research and implementation approach for installation without Fastboot. |
| [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) | Serial boot, RP2040 bridge, Fastboot payload and eMMC access. |
| [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) | FL2 / FL3 parameters and installation research. |
| [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) | Native colour parameters, grid lifecycle, LUT fitting and synthetic dense-chart research. Special thanks to author **Hearts-Ace for substantial support with the training methodology**. |
| [751K/sony-look-bridge](https://github.com/751K/sony-look-bridge) | Sony Edit RAW-development operators and Creative Look matrix/Gamma implementation, used for the native frontend of the M4 computer model. |
| [DavidBuchanan314/fwtool.py](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv) and [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | Firmware container formats and extraction. |
| [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) | Sony camera protocols and firmware research. |
| [q19032/Sony-firmware-unpacker](https://github.com/q19032/Sony-firmware-unpacker) | Firmware decryption and key derivation research. |
| [DavidBuchanan314/Sony-ILCE-7M4-Linux](https://github.com/DavidBuchanan314/Sony-ILCE-7M4-Linux) | Platform Linux reference source. |

Thanks also to the open-source tools and dependencies used by this project. Full attribution, roles and licensing are listed in the [reference register](REFERENCES.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

## Contributing

Issues and pull requests are welcome. For new baselines, include input hashes, address maps and the basis for changes. Do not submit personal private keys, camera calibration, backups or complete firmware. See the [contribution guide](CONTRIBUTING.md).

