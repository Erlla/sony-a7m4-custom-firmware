# Sony A7 IV custom firmware, Fastboot tools and research methods

English · [中文](README.md)

Community research for **Sony ILCE-7M4 (A7 IV / A7M4)**: a compact Windows fastboot host, reviewable source, an SD recovery entry and seven separate modification methods. This project is not affiliated with Sony. Recipes primarily derive from **official A7M4 6.02**, using **FX2 1.01** as the FL2/FL3 donor. Exact supported file hashes are documented per method. Custom features are described by method and validation stage; the final release version is assigned during unified packaging.

## Risk and mandatory backups

**Flashing can permanently brick your camera, destroy calibration or settings, or prevent booting. Incorrect wiring can damage the camera and computer. You assume these risks. Use equipment you can afford to lose.** A valid signature, successful script or visible menu is not proof of safety or complete functionality.

- **Use an original Sony battery for firmware updates, including SD updates and recovery updates. Do not use a third-party battery.** The battery display/caution patch does not waive this requirement. Meet the updater's charge requirement and maintain stable power.
- **Back up your own camera before any write**: every eMMC partition, boot0/boot1, the partition layout and SHA-256 hashes. Keep an additional offline copy. For FL2/FL3, independently back up the physical CP NOR as well. Preserve the original update package, tool revisions, change manifest and rollback images.
- The normal maintenance host requires verified complete backups of the eMMC partitions exposed by the payload from the current connection before maintenance writes, then verifies the entire written partition by readback SHA-256. This is not a raw copy of every chip address. **It excludes separate CP NOR, other MCUs and some hardware state.** It does not guarantee recovery from every failure.
- Maintain reliable power and USB connections. Do not disconnect, power off or force-quit during writes. Never restore another camera's complete settings, calibration or eMMC dump onto your body.
- **A custom flashing cable is required**: a camera Multi-port breakout, an RP2040-Zero boot bridge, common ground and an electrically correct interface. An ordinary USB cable alone is insufficient. Read [wiring](docs/wiring.en.md) first. The camera's Multi-port serial signal level is approximately **3.15 V**; RP2040 is a 3.3 V device. Follow the wiring guide's open-drain configuration and verify signal pull-ups and RESET wiring.
- Fixed binary offsets are specific to the documented model and source hashes. Similar version numbers do not imply compatibility.

## Independent methods (recovery first)

| Method | Separate guide | Included material | Notes and validation limits |
|---|---|---|---|
| 0. One-click recovery through the SD updater | [English](methods/00-sd-recovery/README.en.md) / [中文](methods/00-sd-recovery/README.md) | Six-partition backup, same-body settings preservation, MODE5 trigger, full readback then reboot; camera installs slot1 `BODYDATA.DAT`; read-only connection check and USB failure classification | **Already-fastboot and exact updater allowlist required**. Host cannot read card DAT or confirm installation. [Mechanism and use](methods/00-sd-recovery/README.en.md). |
| 1. Replace the official update key and modify public-key authenticity verification | [English](methods/01-custom-signing/README.en.md) / [中文](methods/01-custom-signing/README.md) | Per-camera PEM replacement, verified four-library `verifyKey` patch, SquashFS/checksum rebuild, maintainer's existing key pair, DAT re-signing utility | Does not install FL2/FL3 automatically. |
| 2. Set the reported firmware version | [English](methods/02-firmware-version/README.en.md) / [中文](methods/02-firmware-version/README.md) | Bounded FAT editing of the two BCD bytes in `updater/dat4`, accepting `0.00`–`9.99` while preserving other contents | Changes the reported version only; does not add newer firmware features. |
| 3. Port and install FL2 / FL3 | [English](methods/03-fl2-fl3/README.en.md) / [中文](methods/03-fl2-fl3/README.md) | AP/CP, donor conversion, configuration and NOR synchronization; **fixed A1 is supported by sample comparisons to Imaging Edge re-selection** | **Default fixed A1**; donor look data comes from FX2. Sample colours approach Edit re-selection, without pixel identity or all-scene FX2 equivalence. [Installation and SD migration repair](methods/03-fl2-fl3/sd-colour-preservation.md). Fresh lossless-RAW samples match all105 main-matrix entries per look; the exact-source RAW recipe is separate from the official6.02 baseline build. |
| 4. Third-party battery percentage/caution restrictions | [English](methods/04-third-party-battery/README.en.md) / [中文](methods/04-third-party-battery/README.md) | 16 AP instructions restoring reported percentage/suppressing caution, preserving authentication state and charging/temperature protection; exact recipes, offline patching and reversal | Independent mechanism, baseline, recipe and validation. Included in SD builds only with `--battery`. **Updates still require an original Sony battery.** |
| 5. Lens AF mechanisms and compatibility capability filtering | [English](methods/05-third-party-lens-af/README.en.md) / [中文](methods/05-third-party-lens-af/README.md) | Separate ID filtering and category/capability/profile range-gate analysis; six CP regions retain reported capabilities/speed profiles, leaving the range gate unchanged; **speed improvements remain untested on hardware** | **No physical focus-speed testing; performance effect unknown.** Independent baseline and validation; SD inclusion requires `--lens-af`. |
| 6. Custom electronic shutter and focus sounds | [English](methods/06-custom-sounds/README.en.md) / [中文](methods/06-custom-sounds/README.md) | Native source, menu/WAV import and persistence, independent slots, volume, restart recovery; exact-layout offline recipe and [test audio](examples/custom-sounds/README.en.md) | File-SHA compatibility, **no firmware version edits**. Reference AP requires the shared menu framework. Reconstructs components, not an installable DAT; single-camera feedback and public rebuild limits are documented. |
| 7. Custom aspect ratios and preview masks | [English](methods/07-custom-aspect-ratios/README.en.md) / [中文](methods/07-custom-aspect-ratios/README.md) / [Implementation (中文)](methods/07-custom-aspect-ratios/IMPLEMENTATION.md) | Adds 17:6, 65:24, 5:4 and 7:6; JPEG/HEIF cropping, original RAW area, labels and Fn icons; exact modification points and camera photos | Landscape/portrait preview accepted on one camera; some settings pages temporarily show 3:2, with masks restored in the shooting view. |

Recovery is separate from the seven firmware modification methods. Normal maintenance retains its full-eMMC-backup and plan-confirmation requirements. Recovery automatically backs up six relevant partitions and permits only its prepared settings candidate; **this is not a complete eMMC/NOR backup**. This publication was checked offline without operating a camera.

## Fixed-condition colour comparison

[Full report: FX2 原厂 / 当前配方](docs/fl23-colour-comparison-20261018/README.md) · [CSV metrics](docs/fl23-colour-comparison-20261018/指标汇总.csv) · [Methods and offline HTML](docs/fl23-colour-comparison-20261018/METHODS.md)

Fixed aperture, shutter, ISO, white balance and lens;8 camera/Edit pairs. Lower native24-patch mean ΔE00 indicates closer agreement with the supplied Edit rendering.

| Recipe | FL mean ΔE00 ↓ | FL2 mean ΔE00 ↓ | FL3 mean ΔE00 ↓ |
| --- | --- | --- | --- |
| FX2 原厂 | 1.444 | 1.565 | 0.951 |
| 当前配方 | 1.444 | 1.233 | 0.678 |

![Two-recipe comparison](docs/fl23-colour-comparison-20261018/assets/summary.png)

FL, FL2 and FL3 are compared together. Both FL means are about1.444; the current recipe is closest for FL2/FL3 in this scene/light, with FL2 yellow/orange residuals. All captures are from A7M4; these are not physical FX2-camera comparisons or general colour-accuracy rankings.

## Fastboot host

Includes full backup, version inspection/editing, custom updater preparation, same-camera backup restoration and restoration of official verification. Chinese BAT entry points are in `advanced/`. **There is no interactive UART console, serial shell, arbitrary UART command interface or serial update-mode switch.** RP2040 serial boot transport remains necessary to enter fastboot; it is not an interactive camera console.

Requirements: Windows 10/11 and Python 3.11+. After cloning:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Follow [setup and external resources](docs/setup.en.md) for fastboot, RP2040 UF2, camera boot payload, driver and SquashFS utilities. External binaries, complete Sony firmware and camera dumps are not bundled.

```powershell
# Synthetic camera only: no hardware, driver or serial operations
.\.venv\Scripts\python.exe -m a7m4 --demo maintain
# Check local resources without operating devices
.\.venv\Scripts\python.exe -m a7m4 doctor
# Real hardware: enter fastboot, complete a full backup, then show maintenance
.\.venv\Scripts\python.exe -m a7m4 maintain
```

Alternatively, run `setup.bat`, then `advanced/进阶维护菜单.bat`. A write plan shows its partition, source/output hashes and an exact plan-bound confirmation string. `maintain --already-fastboot` skips boot preparation while retaining the complete backup requirement.

## Public keys and distribution scope

The maintainer explicitly authorized publication of their previously used [RSA key pair](keys/published/README.md). **The private key is public. Anyone can sign with it, so signatures accepted by this key cannot authenticate the publisher.** Inspect and build packages yourself. Generate a new private identity if you need independent signing authority.

This repository publishes original host code, patch recipes, documentation, the specified research keys and [three user-authorized WAV samples](examples/custom-sounds/README.en.md). Obtain Sony firmware, donor curves/matrices, camera calibration, backups and external drivers separately. Original source uses [MIT](LICENSE); third-party material retains its own terms, described in [third-party notices](THIRD_PARTY_NOTICES.md). Some public research upstreams have no explicit redistribution license; they are linked instead of rebundled as MIT payloads.

## References and acknowledgements

Projects directly used or referenced for this release are listed below. [The full reference register](REFERENCES.md) explains their roles, recorded revisions, runtime dependencies and research-only tools.

| Project | Use |
|---|---|
| [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) | serial boot, RP2040 bridge, camera fastboot payload and eMMC access. |
| [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) | A7C II FL2/FL3 parameter and installation research; historical0.1.0 recipe used as an A7M4 comparison. No upstream USB payload/code vendored. |
| [DavidBuchanan314/fwtool.py, a7iv branch](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv) and [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | firmware container formats and extraction. |
| [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) | Sony camera protocols and firmware research. |
| [ExifTool](https://exiftool.org/) and its [Sony LensType2 table](https://exiftool.org/TagNames/Sony.html) | lens ID category research, not a substitute for actual lens telemetry. |
| [q19032/Sony-firmware-unpacker](https://github.com/q19032/Sony-firmware-unpacker) | firmware decryption and key derivation research. |
| [DavidBuchanan314/Sony-ILCE-7M4-Linux](https://github.com/DavidBuchanan314/Sony-ILCE-7M4-Linux) | platform Linux reference source. |
| [AOSP fastboot](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/) and [squashfs-tools-ng](https://github.com/AgentD/squashfs-tools-ng) | USB host tooling and updater filesystem rebuilding. |
| [arduino-pico](https://github.com/earlephilhower/arduino-pico), [Pico SDK](https://github.com/raspberrypi/pico-sdk) | RP2040 build dependencies. |
| [pySerial](https://github.com/pyserial/pyserial), [pyelftools](https://github.com/eliben/pyelftools), [cryptography](https://github.com/pyca/cryptography) | host runtime dependencies. |
| [Dissect](https://github.com/fox-it/dissect), [PyCryptodome](https://github.com/Legrandin/pycryptodome), [Capstone](https://github.com/capstone-engine/capstone), [Unicorn](https://github.com/unicorn-engine/unicorn), [Keystone](https://github.com/keystone-engine/keystone) | offline filesystem/container work, disassembly, instruction replay and patch research. |
| [Python](https://github.com/python/cpython), [pytest](https://github.com/pytest-dev/pytest), [setuptools](https://github.com/pypa/setuptools) | language, tests and packaging. |
| [NumPy](https://github.com/numpy/numpy), [Dissect extfs](https://github.com/fox-it/dissect.extfs), [util](https://github.com/fox-it/dissect.util), [cstruct](https://github.com/fox-it/dissect.cstruct) | optional complete firmware build dependencies. |
| [Arduino CLI](https://github.com/arduino/arduino-cli), [GCC](https://gcc.gnu.org/), [GNU Binutils](https://www.gnu.org/software/binutils/) | external bridge/payload build tools; [OpenSSL](https://github.com/openssl/openssl), [cffi](https://github.com/python-cffi/cffi), [pycparser](https://github.com/eliben/pycparser), [pip](https://github.com/pypa/pip): cryptography and installation dependencies. |
| [Pillow](https://github.com/python-pillow/Pillow), [Matplotlib](https://github.com/matplotlib/matplotlib) | Offline photo decoding, independent histogram checks and report figures; not host runtime dependencies. |
| [Sharma / Wu / Dalal CIEDE2000](https://hajim.rochester.edu/ece/sites/gsharma/ciede2000/) | 34 reference pairs for colour-difference formula validation; research reference, not code redistribution. |

## Validation and contributions

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python tools/check_public_tree.py
```

Automated tests use synthetic data and never connect to a camera. Method guides and [validation notes](docs/validation.md) distinguish historical user feedback, current offline reproduction and unresolved checks. The extracted host has not completed a new physical flashing acceptance test. Contributions for new baselines should include input hashes, address mapping, differences and verification evidence. Do not submit other people's keys, camera personalization or complete firmware.
