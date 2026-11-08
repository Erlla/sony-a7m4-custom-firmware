# Third-party notices / 第三方说明

Original host code, offline builders, patch recipes and documentation in this repository are distributed under [MIT](LICENSE). Existing author notices are retained. The complete attribution register is [REFERENCES.md](REFERENCES.md).

The MIT grant does not relicense Sony firmware, extracted libraries, donor color/gamma data, camera personalization, Google SDK components, external payloads or other third-party software. The maintainer requested publication of exactly the two historical boot assets under `fastboot/assets/`, with their source material and identities. These external components retain the licensing status described in [fastboot/SOURCES.md](fastboot/SOURCES.md), rather than this project’s MIT grant. Full camera images, Sony libraries, donor data, SDK drivers and host executables remain outside the source tree. The publication checker allows only the two named, hash-pinned boot assets.

## Research upstreams and external executables

- The Windows x64 portable Release archive includes the official CPython embeddable runtime and dependency wheels with their license files, selected Fastboot binaries with the Platform Tools NOTICE, and SquashFS tools with their library licenses and corresponding source archives. These runtime files remain outside the source repository.
- Portable WinUSB setup uses the unmodified signed Zadig installer from pbatard/libwdi, its project license texts, a Fastboot device preset and the corresponding source archive. The Google SDK USB-driver package is not bundled in this portable variant. New-PC installation requires the user's administrator confirmation; driver-signature enforcement remains enabled.

- ILCE-7M4-RE: the historical checkout had no explicit license. The current upstream top-level notice refers to per-directory terms; its Fastboot notice discusses MIT practice and possible GPL-2.0 reference content without providing a single clear license. The historical bridge has no separate license. Preserve original notices and the source record in [fastboot/SOURCES.md](fastboot/SOURCES.md); this repository makes no MIT grant for those components. The host protocol implementation remains independently authored.
- AOSP fastboot source: Apache-2.0 and component-specific notices. Do not assume an SDK-packaged executable and its DLLs can be redistributed merely because source exists elsewhere.
- Google USB Driver: supplied under Android SDK terms, not presented as open source. No INF/catalog/DLL bundle is published here; no driver-signature-enforcement bypass is provided.
- squashfs-tools-ng 1.3.2: CLI tools GPL-3.0-or-later, libsquashfs LGPL-3.0-or-later. External local binaries must retain their license material. If you distribute such binaries, satisfy corresponding-source and dependency-notice requirements; a link alone may be insufficient. Compression/library dependencies keep their own licenses.
- RP2040 toolchain: arduino-pico has mixed core/library notices; Pico SDK is BSD-3-Clause with bundled notices. GCC/Binutils and Arduino CLI retain their own terms. The local historical UF2/payload have not been demonstrated reproducibly identical to a clean upstream checkout.

- [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research): A7C II research reference and historical0.1.0 recipe comparison. Its newly authored code is MIT; no source/payload is copied here. Its Sony firmware, colour data and separately supplied profiles are not covered by this repository's MIT license.

## Python distributions

The core runtime uses pySerial 3.5 (BSD-3-Clause), pyelftools 0.32 (public-domain/license dedication details upstream), and cryptography 46.0.3 (Apache-2.0 or BSD-3-Clause). CPython uses the PSF license and included notices. cryptography's wheel/build dependencies, including OpenSSL, Rust components, cffi and pycparser, have their own notices.

Optional firmware builders use NumPy and Dissect extfs/util/cstruct. Tests use pytest and its dependencies. Installation retrieves their distributions separately. Refer to the links in [REFERENCES.md](REFERENCES.md) and the installed packages' license files for exact terms. A future bundled executable must carry its actual resolved distribution notices; this repository does not declare a mixed dependency bundle entirely MIT.

## Explicit public signing-key exception

The owner explicitly authorized publication of exactly the existing two PEM files in [keys/published](keys/published/README.md). They are provided for unrestricted experimental use as public test material. **The private key is intentionally public and provides no confidentiality or publisher authentication.** This exception is limited to that pair and does not permit publishing unrelated credentials or private keys.

## 中文说明

MIT 仅覆盖本仓库原创主机代码、构建器、补丁配方和文档。完整索尼固件、供体颜色数据、个人备份和第三方驱动未纳入发行。维护者指定公开的两个历史启动文件及源码资料单列于 fastboot/，不改为本项目 MIT 许可；上游许可现状及构建来源见该目录说明。指定的一对实验 PEM 经所有者授权公开，可自由用于实验；私钥已不具备任何保密性或发布者身份保证，不能据此提交其他凭据。

## Native sound adapters

`native/custom-sounds/` contains this project's original adaptation code and link bindings. Rebuilds use external Zig/Clang/LLVM and ARM GCC/Binutils; those distributions are not included and keep their upstream terms. The sound recipe references original unchanged file ranges by COPY and distributes bounded changed-byte ADDs; it does not include complete Sony libraries, factory audio or firmware containers. This does not relicense the original firmware inputs, which users must supply separately.

## Reference sound samples / 参考音频

The user supplied and explicitly authorized public distribution of exactly `YEAH.WAV`, `DAGOU.WAV` and `JIAO.WAV` for reference and testing in [examples/custom-sounds](examples/custom-sounds/README.en.md). These files are distributed unchanged, with audio parameters and SHA-256 checksums in that directory. The MIT license for this project's original code does not automatically apply to these audio files; their existing rights remain with the respective rights holders.

[示例目录](examples/custom-sounds/README.md)中的 `YEAH.WAV`、`DAGOU.WAV` 和 `JIAO.WAV` 由用户提供并明确授权随仓库公开，供参考与测试。三个文件均保持原始字节，附音频参数和 SHA-256。仓库原创代码的 MIT 许可不自动适用于这些音频，原有权利归相应权利人所有。

## Aspect-ratio reference photographs / 纵横比参考照片

The maintainer supplied and explicitly authorized public display of the two camera photographs in [method7](methods/07-custom-aspect-ratios/README.en.md). Public copies remove location and other metadata while preserving compressed image data and decoded pixels. The project's code license does not automatically relicense these photographs; existing rights remain with their respective holders.

[方法7](methods/07-custom-aspect-ratios/README.md)中的两张相机照片由维护者提供并授权公开展示。公开副本去除了定位等元数据，压缩图像与解码像素保持不变。原创代码的MIT许可不自动适用于照片，原有权利归相应权利人所有。

## LUT training results / LUT训练结果

The maintainer authorized publication of the numerical evaluations and generated RGB diagnostic plots in [the training report](docs/custom-lut-training/README.en.md). This update includes no look parameter JSONs, source photographs, reference TIFFs, model weights, Sony programs or extracted constants. Look JSON files will be handled separately through Releases.

[751K/sony-look-bridge](https://github.com/751K/sony-look-bridge) supplies research and MIT-licensed implementations used by the local M4 model's native frontend. This publication vendors no upstream code. Its MIT license does not extend to Sony executables or constants. [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) remains credited for native-parameter references and fitting research.

维护者授权公开[训练报告](docs/custom-lut-training/README.md)中的数值评估和生成的RGB统计图。本次不包含滤镜参数JSON、原片、目标TIFF、权重、Sony程序或常量；滤镜文件由维护者后续通过Releases提供。751K项目为本地模型原生前段提供研究与实现参考；报告公开不改变相关第三方内容的原有权利。
