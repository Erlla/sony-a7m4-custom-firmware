# Third-party notices / 第三方说明

Original host code, offline builders, patch recipes and documentation in this repository are distributed under [MIT](LICENSE). Existing author notices are retained. The complete attribution register is [REFERENCES.md](REFERENCES.md).

The MIT grant does not relicense Sony firmware, extracted libraries, donor color/gamma data, camera personalization, Google SDK components, external payloads or other third-party software. This source repository contains no full camera images, Sony libraries, donor curves/matrices, USB driver package, host executables or RP2040 UF2. Users supply these locally; `.gitignore` and `tools/check_public_tree.py` enforce the publication boundary.

## Research upstreams and external executables

- ILCE-7M4-RE: no explicit license was found in the reviewed source tree. Public availability and attribution are not treated as a redistribution license. Obtain/build the payload and bridge externally; this repository publishes an independent host implementation of the documented wire protocol.
- AOSP fastboot source: Apache-2.0 and component-specific notices. Do not assume an SDK-packaged executable and its DLLs can be redistributed merely because source exists elsewhere.
- Google USB Driver: supplied under Android SDK terms, not presented as open source. No INF/catalog/DLL bundle is published here; no driver-signature-enforcement bypass is provided.
- squashfs-tools-ng 1.3.2: CLI tools GPL-3.0-or-later, libsquashfs LGPL-3.0-or-later. External local binaries must retain their license material. If you distribute such binaries, satisfy corresponding-source and dependency-notice requirements; a link alone may be insufficient. Compression/library dependencies keep their own licenses.
- RP2040 toolchain: arduino-pico has mixed core/library notices; Pico SDK is BSD-3-Clause with bundled notices. GCC/Binutils and Arduino CLI retain their own terms. The local historical UF2/payload have not been demonstrated reproducibly identical to a clean upstream checkout.

## Python distributions

The core runtime uses pySerial 3.5 (BSD-3-Clause), pyelftools 0.32 (public-domain/license dedication details upstream), and cryptography 46.0.3 (Apache-2.0 or BSD-3-Clause). CPython uses the PSF license and included notices. cryptography's wheel/build dependencies, including OpenSSL, Rust components, cffi and pycparser, have their own notices.

Optional firmware builders use NumPy and Dissect extfs/util/cstruct. Tests use pytest and its dependencies. Installation retrieves their distributions separately. Refer to the links in [REFERENCES.md](REFERENCES.md) and the installed packages' license files for exact terms. A future bundled executable must carry its actual resolved distribution notices; this repository does not declare a mixed dependency bundle entirely MIT.

## Explicit public signing-key exception

The owner explicitly authorized publication of exactly the existing two PEM files in [keys/published](keys/published/README.md). They are provided for unrestricted experimental use as public test material. **The private key is intentionally public and provides no confidentiality or publisher authentication.** This exception is limited to that pair and does not permit publishing unrelated credentials or private keys.

## 中文说明

MIT 仅覆盖本仓库原创主机代码、构建器、补丁配方和文档。完整索尼固件、供体颜色数据、个人备份、第三方驱动与 payload 未纳入发行。外部组件按原许可自行取得，公开参考仓库不自动具有再分发许可。指定的一对实验 PEM 经所有者授权公开，可自由用于实验；私钥已不具备任何保密性或发布者身份保证，不能据此提交其他凭据。
