# Reference register / 参考项目清单

整理日期 / Release review: 2026-10-18. 记录此次公开方法和工具实际用到的研究来源、运行依赖与分析工具。历史搜索结果不自动等于使用过的项目；平台参考源码不称为相机固件反编译。 / This register distinguishes research references, runtime components and offline analysis tools. Search hits alone are not attributed as dependencies, and platform source is not represented as decompiled camera firmware.

## 相机研究 / Camera research

| Project | Use / 用途 | Publication treatment / 分发处理 |
|---|---|---|
| [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) | BootROM serial boot, RP2040 bridge, fastboot payload/protocol, eMMC crypto/access, wiring | Reviewed local checkout `2328d18ce640e6c8cd9341efcf0043ce9042a135`; local changes/builds are separate evidence. No explicit license found in that tree. Payload/UF2/source are linked and externally obtained, not copied into this MIT repository. |
| [DavidBuchanan314/fwtool.py — a7iv](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv) | A7 IV firmware format / container extraction reference | Fork and branch identified separately from its ancestor; external tool, not vendored. |
| [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | Sony UFU/firmware format and extraction foundation | Upstream MIT source; attribution retained by reference, not copied here. |
| [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) | A7C II FL2/FL3 parameters, installation research and historical0.1.0 comparison recipe / 参数、安装研究及历史0.1.0对照 | Upstream newly authored code is MIT; no code/payload vendored. A7C II offsets and USB installation are not directly applied to A7M4. Sony firmware/colour data retain their own rights. Current upstream has evolved beyond0.1.0. |
| [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) | Sony camera interfaces, protocol/service and firmware research background | MIT upstream; research reference, not a runtime requirement of this host. |
| [ExifTool](https://exiftool.org/) / [Sony LensType2](https://exiftool.org/TagNames/Sony.html) | Lens ID category cross-checks for the third-party lens research | Reference table, not a runtime dependency or physical lens-test evidence. No source/data table is copied here. |
| [q19032/Sony-firmware-unpacker](https://github.com/q19032/Sony-firmware-unpacker) | Public firmware decryption/key derivation research; credits fwtool | Public reference, not a claim of MIT permission for all attached artifacts. No archive copied. |
| [DavidBuchanan314/Sony-ILCE-7M4-Linux](https://github.com/DavidBuchanan314/Sony-ILCE-7M4-Linux) | Linux/platform source, hardware context | Kernel/reference source under its own per-file terms. Not decompiled firmware or an included payload. |

## 主机与桥接构建 / Host and bridge dependencies

| Project | Role / 用途 |
|---|---|
| [AOSP fastboot](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/) | External USB host executable; source Apache-2.0/component notices; SDK binaries have their own distribution terms. |
| [squashfs-tools-ng 1.3.2](https://github.com/AgentD/squashfs-tools-ng/tree/v1.3.2) | External `sqfs2tar`/`tar2sqfs` processes. Tools GPL-3.0-or-later, libsquashfs LGPL-3.0-or-later. |
| [earlephilhower/arduino-pico](https://github.com/earlephilhower/arduino-pico) | Upstream Arduino RP2040 core, mixed per-component licenses. |
| [raspberrypi/pico-sdk](https://github.com/raspberrypi/pico-sdk) | Upstream bridge/core SDK, BSD-3-Clause plus component notices. |
| [arduino/arduino-cli](https://github.com/arduino/arduino-cli) | External bridge build tool, not required by the Python host once UF2 is built. |
| [GCC](https://gcc.gnu.org/), [GNU Binutils](https://www.gnu.org/software/binutils/) | AArch64/ARM payload compiler, assembler, linker and objcopy. External toolchain with its own GPL/runtime-exception terms. |
| [pySerial](https://github.com/pyserial/pyserial) | 3.5, RP2040 packet transport; BSD-3-Clause. |
| [pyelftools](https://github.com/eliben/pyelftools) | 0.32, ELF symbol/segment parsing; public-domain dedication/license details upstream. |
| [cryptography](https://github.com/pyca/cryptography) | 46.0.3, RSA validation/generation/signatures and AES container codec; Apache-2.0/BSD-3-Clause. |
| [OpenSSL](https://github.com/openssl/openssl), [cffi](https://github.com/python-cffi/cffi), [pycparser](https://github.com/eliben/pycparser) | Cryptography distribution/build dependencies; retain exact installed distribution notices. |
| [NumPy](https://github.com/numpy/numpy) | Optional batch UFU block checks/re-encryption; BSD-3-Clause and bundled notices. |
| [Dissect extfs](https://github.com/fox-it/dissect.extfs), [util](https://github.com/fox-it/dissect.util), [cstruct](https://github.com/fox-it/dissect.cstruct) | Optional ext image parsing, run mapping and supporting structures. Extfs pinned to 3.15 because its internal run mapping is deliberately version-specific. |
| [CPython](https://github.com/python/cpython), [setuptools](https://github.com/pypa/setuptools), [pip](https://github.com/pypa/pip) | Python runtime and source installation/build. |
| [pytest](https://github.com/pytest-dev/pytest) | Test-only dependency, MIT; its resolved dependencies retain their own notices. |

[Google USB Driver](https://developer.android.com/studio/run/win-usb) is an external SDK component **not classified as an open-source project**. It is listed for completeness because the Windows workflow uses its original signed WinUSB binding. It is not bundled here.

## 离线研究工具 / Offline research tools

| Project | Role / 用途 |
|---|---|
| [Dissect FAT](https://github.com/fox-it/dissect.fat), [SquashFS](https://github.com/fox-it/dissect.squashfs) | Historical independent filesystem extraction and audit. The published minimal FAT editor is original code. |
| [PyCryptodome](https://github.com/Legrandin/pycryptodome) | Historical firmware encryption/signing scripts and independent cryptographic checks. The published implementation uses cryptography. |
| [Capstone](https://github.com/capstone-engine/capstone) | ARM/AArch64 disassembly, instruction boundary and patch review. |
| [Unicorn](https://github.com/unicorn-engine/unicorn) | Original getter, selector, consumer and menu instruction replay in bounded synthetic contexts; not full camera emulation. |
| [Keystone](https://github.com/keystone-engine/keystone) | ARM/Thumb/AArch64 patch assembly during research. Final recipes contain the reviewed output bytes and do not require Keystone. |

不复制第三方完整源码、构建环境或大体积二进制。源码许可与工具输出/固件版权分别处理，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。 / No full third-party trees or binary bundles are included. Source licenses and rights in firmware/tool outputs are separate; see the notices.

## 实拍报告工具 / Photo-report tools

| Project | Role |
|---|---|
| [Pillow](https://github.com/python-pillow/Pillow), [Matplotlib](https://github.com/matplotlib/matplotlib) | Offline decoding, independent RGB count/error checks, report plots. Respective upstream licenses; no packages or fonts bundled. |
| [Sharma / Wu / Dalal CIEDE2000](https://hajim.rochester.edu/ece/sites/gsharma/ciede2000/) | Reference validation with34 published test pairs. Website/paper/data cited, not relicensed or bundled. |

## 自定义声音构建 / Custom-sound build

- [Zig](https://github.com/ziglang/zig),0.15.2: external AArch64 freestanding compiler using its Clang/LLVM toolchain; used to reproduce the project's native adapters. Compiler/toolchain files are not bundled. Zig and bundled LLVM/Clang components retain their respective upstream licenses.
- ARM GNU GCC16.1.0 / Binutils: external ARMv7-A Thumb soft-float compilation for the project's CP owner and gain adapters. No compiler binaries or Sony native programs are redistributed.
- Sound C/assembly adapters, SHA-bound file recipes and the PCM/Q24/F0 converter are project-authored code under the root MIT license. Fixed source addresses, wire layouts and validation results are research facts, not original Sony source. Existing references above remain applicable to firmware extraction and offline ELF/native verification.
