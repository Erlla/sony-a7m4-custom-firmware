# Sony A7 IV custom firmware and tools

> **Flashing risk**
>
> Writing or modifying firmware can permanently brick the camera, prevent booting or destroy calibration and settings. Incorrect wiring can damage the camera and computer. You assume the risks of these operations.
>
> **Back up your own camera before any write. Use an original Sony battery for firmware updates.** Maintain stable power and connections throughout writes. Never restore another camera's backup onto your body.

English · [中文](README.md)

**Supported firmware: official V6.02 for Sony ILCE-7M4 (A7 IV / A7M4).**

Provides installation without Fastboot, Fastboot maintenance tools and source for firmware modifications. Supported input hashes are documented in each method guide.

## 1. Install firmware without Fastboot

Use a normal USB data cable and **M4 Camera Tool** to prepare the updater, then install firmware from the camera SD card. The camera must boot normally and enter USB mass-storage mode.

1. Place a compatible `BODYDATA.DAT` in the **root of the card in slot 1**.
2. Connect the camera to the computer with a normal USB cable and select **写入补丁** in M4 Camera Tool.
3. Wait for the tool to explicitly allow updating, disconnect USB, then install through the camera's version / software-update menu.

**[Installation guide](no-fastboot-install/README.en.md)** · [Software guide](no-fastboot-install/TOOL-1.00.md) · [Source and build](no-fastboot-install/software/README.en.md) · [Principle and patch locations](no-fastboot-install/IMPLEMENTATION.md)

**Complete firmware packages are not available yet. They will be provided after all feature updates are complete.** The tool neither supplies nor validates the package; follow the installation guide to check files and prerequisites.

## 2. Fastboot modification methods

The Fastboot route requires a **Multi-port flashing cable and an RP2040-Zero boot bridge**; a normal USB cable is insufficient. Complete [wiring](docs/wiring.en.md), [setup](docs/setup.en.md) and your camera's backup before using a method below. Feature source and installation routes are documented separately; consult each method's integration notes when combining features.

| Method | Function | Guide |
|---|---|---|
| SD update recovery | Trigger the camera's SD recovery updater from Fastboot while preserving same-body settings. | [Instructions](methods/00-sd-recovery/README.en.md) |
| Custom update signing | Replace the update key and modify key verification to support self-signed packages. | [Instructions](methods/01-custom-signing/README.en.md) |
| Firmware version display | Set the firmware version reported by the camera. | [Instructions](methods/02-firmware-version/README.en.md) |
| FL2 / FL3 port | Port the FX2 FL2 and FL3 Creative Looks and associated colour configuration. | [Instructions](methods/03-fl2-fl3/README.en.md) |
| Third-party batteries | Show battery percentage and suppress the caution while retaining charging and temperature protection. Updates still require a Sony battery. | [Instructions](methods/04-third-party-battery/README.en.md) |
| Lens AF capability filtering | Retain lens-reported capabilities and speed profiles; no focus-speed improvement is promised. | [Instructions](methods/05-third-party-lens-af/README.en.md) |
| Custom sounds | Import WAVs from SD for mechanical/electronic shutter sounds, with separate focus sound and volume settings. | [Instructions](methods/06-custom-sounds/README.en.md) |
| Custom aspect ratios | Add 17:6, 65:24, 5:4 and 7:6, with JPEG / HEIF cropping and the original RAW area retained. | [Instructions](methods/07-custom-aspect-ratios/README.en.md) |
| Custom LUTs | Import converted JSON LUTs individually from SD; 16 replaceable slots, eight adjustments plus strength per filter, and approximately one-second loading on first use after power-on. | [Instructions](methods/08-custom-lut/README.en.md) |

### Documentation navigation

| Task | Links |
|---|---|
| Prepare hardware and the host | [Wiring](docs/wiring.en.md) · [Setup and external resources](docs/setup.en.md) |
| Back up, restore and maintain | [Advanced maintenance](advanced/) · [SD update recovery](methods/00-sd-recovery/README.en.md) |
| Combine features and migrate installs | [Custom LUT integration](methods/08-custom-lut/INTEGRATION.md) · [FL2 / FL3 SD migration](methods/03-fl2-fl3/sd-colour-preservation.md) |
| View interfaces and sample files | [LUT interface](methods/08-custom-lut/README.en.md) · [Sound samples](examples/custom-sounds/README.en.md) · [Aspect ratios](methods/07-custom-aspect-ratios/README.en.md) |
| Read technical references | [Colour comparison](docs/fl23-colour-comparison-20261018/README.md) · [Validation notes](docs/validation.md) · [Reference register](REFERENCES.md) |
| Contribute | [Contribution guide](CONTRIBUTING.md) · [Third-party notices](THIRD_PARTY_NOTICES.md) |

### Fastboot tools

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

## Disclaimer and licensing

This community project is not affiliated with Sony. Most recipes derive from **official A7M4 6.02**, with **FX2 1.01** as the FL2 / FL3 colour-data donor. See each method for its supported inputs.

The maintainer explicitly authorized publication of their previously used [RSA key pair](keys/published/README.md). **The private key is public. Anyone can sign with it, so signatures accepted by this key cannot authenticate the publisher.** Inspect and build packages yourself. Generate a new private identity if you need independent signing authority.

This repository publishes original host code, patch recipes, documentation, the specified public keys and [three user-authorized WAV samples](examples/custom-sounds/README.en.md). Obtain Sony firmware, donor curves/matrices, camera calibration, backups and external drivers separately. Original source uses [MIT](LICENSE); third-party material retains its own terms, described in [third-party notices](THIRD_PARTY_NOTICES.md). Some public research upstreams have no explicit redistribution license; they are linked instead of rebundled as MIT payloads.


## Acknowledgements

Thanks to the following projects for sharing the research referenced here:

| Project | Reference |
|---|---|
| [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools) | Research and implementation approach for installation without Fastboot. |
| [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) | Serial boot, RP2040 bridge, Fastboot payload and eMMC access. |
| [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) | FL2 / FL3 parameters and installation research. |
| [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) | Native colour parameters, grid lifecycle research and R5ColorLab's LUT-fitting approach. |
| [DavidBuchanan314/fwtool.py](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv) and [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | Firmware container formats and extraction. |
| [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) | Sony camera protocols and firmware research. |
| [q19032/Sony-firmware-unpacker](https://github.com/q19032/Sony-firmware-unpacker) | Firmware decryption and key derivation research. |
| [DavidBuchanan314/Sony-ILCE-7M4-Linux](https://github.com/DavidBuchanan314/Sony-ILCE-7M4-Linux) | Platform Linux reference source. |

Thanks also to the open-source tools and dependencies used by this project. Full attribution, roles and licensing are listed in the [reference register](REFERENCES.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

## Contributing

Issues and pull requests are welcome. For new baselines, include input hashes, address maps and the basis for changes. Do not submit personal private keys, camera calibration, backups or complete firmware. See the [contribution guide](CONTRIBUTING.md).
