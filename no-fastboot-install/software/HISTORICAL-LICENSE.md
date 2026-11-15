# Historical camera-side helper licensing / 历史相机端辅助代码许可

## Scope / 适用范围

At commit `d849c6074a0da9433e24288eee2ef64e3b7561bd`, the maintainer-owned original portions of the five files below are covered by the **MIT License**. This grant includes modified source and the corresponding code in compiled binaries. Their execution on the camera, including compilation as an uploaded helper, is covered by this MIT grant. This records the maintainer's [Issue #30 clarification](https://github.com/Erlla/sony-a7m4-custom-firmware/issues/30#issuecomment-6886625848).

提交 `d849c6074a0da9433e24288eee2ef64e3b7561bd` 中，下列五个文件由维护者拥有版权的原创部分按 **MIT 许可**授权，包括修改后的源码及编译后二进制中的相应代码。该授权覆盖在相机端运行及编译为上传辅助程序的形式。本说明将维护者在 Issue #30 中的授权澄清记录于仓库。

Paths are relative to `no-fastboot-install/software/app/`. Hashes identify the exact Git blob bytes in that snapshot.

路径相对于 `no-fastboot-install/software/app/`，SHA-256 对应指定提交中的精确 Git 文件内容。

| File / 文件 | SHA-256 |
| --- | --- |
| `native/bootstrap.c` | `4e4dcb37eceab654a25b4a7f0d16626d1764f2a9708a48b3275da10c173b19a1` |
| `native/lifecycle_worker.c` | `a2b3d5ad35f50ebd7d32711fd4ffd67d681d4ccc62d1270e2e1585e78457852b` |
| `native/linux_a64.h` | `827bfa50c9d5e2a1ee8eacc032303844cd3c0a8a9b4f5ea1bfa640a987eedd88` |
| `writer/writer.c` | `e2ce0a4132c579d1597e0260f8119de942e31c67bed40881cb800480e65572f3` |
| `writer/sha256.h` | `92a12379679d481d512e55a6928bf71825651a346d39b2ad15b9bafdea851ae5` |

Historical MIT grants continue under their existing terms. Later original additions and changes follow the repository's applicable licensing declarations. Third-party portions follow their own grants. Manufacturer firmware, generated inputs and separately distributed dependencies require their respective permissions and notices.

历史 MIT 授权持续按其原有条款适用，后续新增原创内容及修改按仓库对应许可声明处理。第三方部分沿用原授权，厂商固件、生成输入及另行分发的依赖分别遵守相应权限和声明。

## Source review and attribution / 来源核对与署名

The public history first adds all five files in commit `fb4e1b1`. Review of the pinned source, available earlier local development files and referenced native implementations identified the following matches.

- `native/linux_a64.h` contains an `sc()` AArch64 syscall wrapper whose C tokens match the wrapper in the pinned upstream `installer.c`, with whitespace differences.
- `writer/sha256.h` shares several implementation sequences with the pinned upstream `sha256.h`, including initialization, compression-round and state-update code. Its state layout, identifiers and final-padding implementation also differ. The shared FIPS constants alone do not determine implementation authorship.
- `native/bootstrap.c` and `native/lifecycle_worker.c` include `linux_a64.h`. `writer/writer.c` includes the lifecycle source and `sha256.h`, so the relevant notices accompany distributions incorporating those helpers.

The referenced upstream is **QAQLeonard/a7c2-fl23-research**, now named **QAQLeonard/a7c2-tools**, at commit `0bf1dbb68298bc2e6e643bfd8ce44aee6615cae6`. Its newly authored software is MIT-licensed. The upstream copyright notice is retained below for the matching helper/reference implementation. [Upstream installer](https://github.com/QAQLeonard/a7c2-tools/blob/0bf1dbb68298bc2e6e643bfd8ce44aee6615cae6/src/fl23/native/installer.c) · [Upstream SHA-256](https://github.com/QAQLeonard/a7c2-tools/blob/0bf1dbb68298bc2e6e643bfd8ce44aee6615cae6/src/fl23/native/sha256.h) · [Upstream license](https://github.com/QAQLeonard/a7c2-tools/blob/0bf1dbb68298bc2e6e643bfd8ce44aee6615cae6/LICENSE)

The ABI definitions reference Linux AArch64 interfaces, and the SHA-256 algorithm follows FIPS 180-4. These references provide the interface and algorithm specifications. The initial public import and available development records provide only a partial provenance history. This review identified the matches above, with no additional third-party implementation or required notice identified within the reviewed material. [Linux AArch64 interface](https://github.com/torvalds/linux/blob/v4.9/arch/arm64/include/uapi/asm/fcntl.h) · [FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)

公开历史中五个文件均首次加入于 `fb4e1b1`。指定快照、已有早期本地开发文件及参考实现的核对，发现 `linux_a64.h` 的 `sc()` 封装与上述上游实现的 C 记号一致，仅有空白差异。`sha256.h` 的初始化、压缩轮和状态更新也存在多个匹配片段，同时具有结构布局、命名和填充实现差异。这里保留对应的上游 MIT 版权声明。其他三个文件通过包含关系使用这些辅助代码，分发时一并携带相应声明。

Linux AArch64 接口和 FIPS 180-4 为 ABI 与算法参考。已有公开导入和开发记录提供的来源链仍不完整。本次审查范围内已识别上述匹配，尚未识别出额外的第三方实现或所需声明。

## Notices to retain / 分发时保留的声明

Retain both copyright lines and the complete MIT permission and warranty text below with source distributions and distributions containing the applicable compiled portions. The A7M4 line identifies the project's original portions, and the A7C II line preserves upstream attribution for the helper/reference implementation described above.

源码及包含相应编译代码的分发应保留下列两行版权声明和完整 MIT 授权、免责文字。A7M4 版权行对应本项目原创部分，A7C II 版权行保留上述辅助代码参考实现的上游署名。

```text
MIT License

Copyright (c) 2026 A7M4 Fastboot Toolkit contributors
Copyright (c) 2026 A7C II FL2/FL3 preview contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
