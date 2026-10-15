# 方法 1：替换更新公钥与修改公钥真实性验证

[English](README.en.md) · [总说明与刷机风险](../../README.md)

本方法只改变更新器的信任配置。目标是让 A7M4 接受由自有 RSA 密钥签名的升级包，不包含版本改写或 FL2/FL3 功能修改。

## 原理：两个不同的检查

1. 更新器从 `nflasha1` 的 FAT 文件 `boot/initrd.img` 加载 SquashFS，其中 `/etc/VerificationKey.pem` 是升级包验签公钥。
2. `Updater::SignatureVerification::verifyKey(char const*)` 对公钥本身进行真实性检查。已有逆向记录表明此路径涉及 PEM 的 SHA-1 与跨处理器返回值（请求 `0x025906BE`）；仅替换 PEM，会在这一步被原厂信任检查拒绝。这里不声称已完整还原远端信任根实现。
3. 对以下四库中同名函数的入口写入 AArch64 `mov w0,#0; ret`，让该项检查返回成功；同时将 PEM 换成自己的公钥。
4. 升级包自身的 **RSA-2048 / PKCS#1 v1.5 / SHA-256 签名检查仍然保留**。DAT 必须使用对应私钥签名，并满足模型、版本、各层校验及安装条件。此补丁不等于关闭 BootROM Secure Boot，也不等于接受任意损坏的包。

| initrd 内路径 | 6.02 的函数文件偏移 |
|---|---:|
| `usr/lib/libsdfileinputupdaterapi.so` | `0xA9A8` |
| `usr/lib/libseninputupdaterapi.so` | `0x5244` |
| `usr/lib/libupdaterapi.so` | `0x13324` |
| `usr/lib/libuudfileinputupdaterapi.so` | `0x95AC` |

入口字节为 `00 00 80 52 C0 03 5F D6`。偏移针对 6.02 的库文件，不是分区偏移。本项目实际通过 ELF 动态符号、可执行 PT_LOAD 映射、原函数完整 SHA-256 白名单定位，拒绝未知实现。白名单见 [updater.json](../../a7m4/profiles/updater.json)，实现见 [patching.py](../../a7m4/patching.py)。

原厂公钥 DER SHA-256：`be79b3323d7d92dff52175fc6d12825d73cfc68c32e4fcbca5c7d36fc04bdf10`。此指纹用于识别已审查基线，不是上面的 SHA-1 检查值。

## 使用步骤

先完成 [环境准备](../../docs/setup.md)、[自制刷机线](../../docs/wiring.md) 和自己的完整备份。离线生成独立密钥，或明确选用维护者已公开的实验公钥：

```powershell
python -m a7m4.offline keygen local/my-keys
# 离线构建；不连接相机。输入应是本机未改动更新器的完整备份
python -m a7m4.offline unlock local/my-backup/nflasha1.bin --public-key local/my-keys/updater-public.pem --output output/nflasha1-custom.bin
```

构建器读取 FAT 簇链、校验旧 initrd MD5 与 `p1chksum`，保留 TAR/POSIX 元数据，修改一个 PEM 和四个库，重建 SquashFS 后再次解包逐项核对内容与元数据，最后更新 `p1chksum`。只在原分配范围内替换，超出容量或出现未知格式会中止；不会格式化 FAT。

实机安装可直接使用同一构建逻辑：

```powershell
python -m a7m4 maintain --action unlock
```

该命令先完成本次连接的完整备份，再询问**公钥路径**，显示本机生成的写入计划，精确确认后只写 `nflasha1`，随后全分区读回。也可双击 `advanced/刷入验签跳过版更新器.bat`。私钥不需要连接相机，也不会被写进 initrd。

## 维护者原有密钥对

[keys/published](../../keys/published/README.md) 存放维护者原来实际使用并授权公开的密钥对。

- 公钥 PEM 文件 SHA-256：`c39f3d878e129bbac87ad346182df754d7dd99d80c35c38bbb6517e37ca8e449`。
- 公钥 DER SHA-256：`eed3fd52e3adc60ef13b584bc0b50345ee96639be81efa02e0031a6eccc65e76`。
- 算法：RSA-2048，公钥指数 65537。

**该私钥已公开，任何人都能伪造其签名身份。** 如选择安装此公钥，应自行核对升级包的来源、构建和内容；签名通过不提供发布者身份保证。自己的新私钥应留在 `local/` 等忽略目录，不提交到 Git。

## DAT 签名与封装

`a7m4.offline resign` 可以为**已经正确封装**的 UFU/DAT 重新签名：

```powershell
python -m a7m4.offline resign local/prepared.DAT --private-key keys/published/A7M4_updater_private.pem --output output/BODYDATA.DAT
```

工具解析 UFU 大端长度/标签，定位 FDAT 末尾 16 字节 IV 和 256 字节签名；对 `FDAT 密文 || IV` 的 SHA-256 做 PKCS#1 v1.5 签名，更新覆盖 DEND 前全部字节的 CRC32，并立即验证新签名。不会打印密钥内容。

**重新签名不会修复错误的内层包。** 若改变明文，需要更新镜像 CRC 清单、UDTRFIRM 头 CRC、UFU 1024 字节块校验，并按原 AES/帧格式重加密。此过程的独立代码在 [firmware.py](../../a7m4/firmware.py)。单独给原厂 DAT 重签名，也不会自动让尚未改过信任配置的相机接受它。

## 恢复与边界

用 `python -m a7m4 maintain --action restore_official` 或对应 BAT 选择**同机、同固件基线、改动前的完整备份**。工具校验备份绑定及除 PEM/入口补丁外的逻辑文件与元数据一致性，拒绝用另一个版本的更新器覆盖当前基线。

6.04/6.05 自签包的历史安装与用户反馈证明这条信任修改路线曾在维护者机身使用。精简后的新主机程序目前只完成离线测试，不能把旧脚本实机成功等同于本程序已实机验收。未知固件白名单、所有升级渠道、后续原厂升级会否覆盖公钥，均需要重新核验。
