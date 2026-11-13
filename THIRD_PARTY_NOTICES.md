# Third-party notices / 第三方说明

Copyright (c) 2026 A7M4 Fastboot Toolkit contributors.

New original host code, offline builders, patch recipes and documentation published from this license change use the [GNU GPLv3 (GPL-3.0-only)](LICENSE). Previously MIT-licensed material and contributions retain their [historical MIT grants](LICENSE-MIT-LEGACY). Existing author notices are retained. The complete attribution register is [REFERENCES.md](REFERENCES.md).

Sony firmware, extracted libraries, donor color/gamma data, camera personalization, Google SDK components, external payloads and other third-party software follow their respective terms. The maintainer requested publication of exactly the two historical boot assets under `fastboot/assets/`, with their source material and identities. The licensing status of these external components is described in [fastboot/SOURCES.md](fastboot/SOURCES.md). Full camera images, Sony libraries, donor data, SDK drivers and host executables remain outside the source tree. The publication checker allows only the two named, hash-pinned boot assets.

## Research upstreams and external executables

- The Windows x64 portable Release archive includes the official CPython embeddable runtime and dependency wheels with their license files, selected Fastboot binaries with the Platform Tools NOTICE, and SquashFS tools with their library licenses and corresponding source archives. These runtime files remain outside the source repository.
- Portable WinUSB setup uses the unmodified signed Zadig installer from pbatard/libwdi, its project license texts, a Fastboot device preset and the corresponding source archive. The Google SDK USB-driver package is not bundled in this portable variant. New-PC installation requires the user's administrator confirmation; driver-signature enforcement remains enabled.

- ILCE-7M4-RE: the historical checkout had no explicit license. The current upstream top-level notice refers to per-directory terms; its Fastboot notice discusses MIT practice and possible GPL-2.0 reference content without providing a single clear license. The historical bridge has no separate license. Preserve original notices and the source record in [fastboot/SOURCES.md](fastboot/SOURCES.md); those components follow the scope recorded there. The host protocol implementation remains independently authored.
- AOSP fastboot source: Apache-2.0 and component-specific notices. Do not assume an SDK-packaged executable and its DLLs can be redistributed merely because source exists elsewhere.
- Google USB Driver: supplied under Android SDK terms, not presented as open source. No INF/catalog/DLL bundle is published here; no driver-signature-enforcement bypass is provided.
- squashfs-tools-ng 1.3.2: CLI tools GPL-3.0-or-later, libsquashfs LGPL-3.0-or-later. External local binaries must retain their license material. If you distribute such binaries, satisfy corresponding-source and dependency-notice requirements; a link alone may be insufficient. Compression/library dependencies keep their own licenses.
- RP2040 toolchain: arduino-pico has mixed core/library notices; Pico SDK is BSD-3-Clause with bundled notices. GCC/Binutils and Arduino CLI retain their own terms. The local historical UF2/payload have not been demonstrated reproducibly identical to a clean upstream checkout.

- [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research): A7C II research reference and historical0.1.0 recipe comparison. Its newly authored code is MIT; no source/payload is copied here. Its Sony firmware, colour data and separately supplied profiles are not covered by this repository's project license.

## Python distributions

The core runtime uses pySerial 3.5 (BSD-3-Clause), pyelftools 0.32 (public-domain/license dedication details upstream), and cryptography 46.0.3 (Apache-2.0 or BSD-3-Clause). CPython uses the PSF license and included notices. cryptography's wheel/build dependencies, including OpenSSL, Rust components, cffi and pycparser, have their own notices.

Optional firmware builders use NumPy and Dissect extfs/util/cstruct. Tests use pytest and its dependencies. Installation retrieves their distributions separately. Refer to the links in [REFERENCES.md](REFERENCES.md) and the installed packages' license files for exact terms. A future bundled executable must carry its actual resolved distribution notices; the licenses of a mixed dependency bundle must be evaluated by component.

## Explicit public signing-key exception

The owner explicitly authorized publication of exactly the existing two PEM files in [keys/published](keys/published/README.md). They are provided for unrestricted experimental use as public test material. **The private key is intentionally public and provides no confidentiality or publisher authentication.** This exception is limited to that pair and does not permit publishing unrelated credentials or private keys.

## 中文说明

本次许可变更后的新增原创主机代码、构建器、补丁配方和文档采用 [GNU GPLv3（GPL-3.0-only）](LICENSE)。已按 MIT 发布的内容和贡献继续按 [历史 MIT 许可](LICENSE-MIT-LEGACY) 授权。完整索尼固件、供体颜色数据、个人备份和第三方驱动未纳入发行。维护者指定公开的两个历史启动文件及源码资料单列于 fastboot/，按该目录记录的上游许可范围和构建来源处理。指定的一对实验 PEM 经所有者授权公开，可自由用于实验；私钥已不具备任何保密性或发布者身份保证，不能据此提交其他凭据。

## Native sound adapters

`native/custom-sounds/` contains this project's original adaptation code and link bindings. Rebuilds use external Zig/Clang/LLVM and ARM GCC/Binutils; those distributions are not included and keep their upstream terms. The sound recipe references original unchanged file ranges by COPY and distributes bounded changed-byte ADDs; it does not include complete Sony libraries, factory audio or firmware containers. This does not relicense the original firmware inputs, which users must supply separately.

## Reference sound samples / 参考音频

The user supplied and explicitly authorized public distribution of exactly `YEAH.WAV`, `DAGOU.WAV` and `JIAO.WAV` for reference and testing in [examples/custom-sounds](examples/custom-sounds/README.en.md). These files are distributed unchanged, with audio parameters and SHA-256 checksums in that directory. These audio files follow their separate authorization, with existing rights held by their respective rights holders.

[示例目录](examples/custom-sounds/README.md)中的 `YEAH.WAV`、`DAGOU.WAV` 和 `JIAO.WAV` 由用户提供并明确授权随仓库公开，供参考与测试。三个文件均保持原始字节，附音频参数和 SHA-256。这些音频按单独授权提供，原有权利归相应权利人所有。

## Aspect-ratio reference photographs / 纵横比参考照片

The maintainer supplied and explicitly authorized public display of the two camera photographs in [method7](methods/07-custom-aspect-ratios/README.en.md). Public copies remove location and other metadata while preserving compressed image data and decoded pixels. The project's code license does not automatically relicense these photographs; existing rights remain with their respective holders.

[方法7](methods/07-custom-aspect-ratios/README.md)中的两张相机照片由维护者提供并授权公开展示。公开副本去除了定位等元数据，压缩图像与解码像素保持不变。这些照片按单独授权提供，原有权利归相应权利人所有。

## LUT training results / LUT训练结果

The maintainer authorized publication of the numerical evaluations and generated RGB diagnostic plots in [the training report](docs/custom-lut-training/README.en.md). That earlier result-only publication included no look parameter JSONs, source photographs, reference TIFFs, model weights, Sony programs or extracted constants. Look JSON files will be handled separately through Releases.

[751K/sony-look-bridge](https://github.com/751K/sony-look-bridge) supplies research and MIT-licensed implementations used by the local M4 model's native frontend. Training source now vendors the pinned MIT Python implementation with its licence under training/third_party; Sony executables/constants remain externally supplied. Its MIT license does not extend to Sony executables or constants. [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) remains credited for native-parameter references and fitting research.

维护者授权公开[训练报告](docs/custom-lut-training/README.md)中的数值评估和生成的RGB统计图。此前结果页发布不包含滤镜参数JSON、原片、目标TIFF、权重、Sony程序或常量；滤镜文件由维护者后续通过Releases提供。751K项目为本地模型原生前段提供研究与实现参考；报告公开不改变相关第三方内容的原有权利。


## LUT training source and asset separation

The training method, frozen M4 model contract, native JSON codec, empirical response architecture and optimisation primitives are organised under [training](training/README.en.md). The pinned Sony Look Bridge source retains [its MIT licence](training/third_party/SONY_LOOK_BRIDGE_LICENSE). No Sony executable, extracted Sony table or personal camera photograph is added to source history.

Frozen empirical model files and synthetic RAW chart/target samples are prepared as separate training assets. SHA-256 identities and data roles are recorded; publication does not relabel upstream chart authorship or grant a new licence to Sony software. Historical result-only publication statements above describe those earlier materials. Finished filter JSONs remain separate Release content.

特别感谢 [Hearts-Ace](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) 对训练方法的大力支持，包括原生参数、网格搜索与合成大色卡研究；M4响应仍由本项目的M4标定提供。已有上游许可和归属保持。
