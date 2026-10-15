# Method 1: replace the update key and modify key authenticity verification

[中文](README.md) · [Risks and backups](../../README.en.md)

This method changes the updater's trust configuration so that it can accept packages signed by an owner-controlled RSA key. It does not modify reported versions or install FL2/FL3.

## Two separate checks

`nflasha1` contains a FAT file `boot/initrd.img`. Its SquashFS contains `/etc/VerificationKey.pem`, the package verification public key. Replacing this PEM alone is insufficient: `Updater::SignatureVerification::verifyKey(char const*)` checks authenticity of the key itself. Existing reverse-engineering evidence associates that path with a PEM SHA-1 check and an interprocessor response to request `0x025906BE`; the complete remote trust-root implementation has not been reconstructed here.

Replace the PEM and overwrite the entry of `verifyKey` in all four updater libraries with AArch64 `mov w0,#0; ret`: bytes `00 00 80 52 C0 03 5F D6`. This returns success for key authenticity. **Package RSA-2048 / PKCS#1 v1.5 / SHA-256 verification remains active.** Packages must still use the matching private key and satisfy model, version, integrity and installation requirements. This is not a BootROM Secure Boot disable or permission to install corrupt containers.

| Path inside initrd | File offset on the reviewed 6.02 baseline |
|---|---:|
| `usr/lib/libsdfileinputupdaterapi.so` | `0xA9A8` |
| `usr/lib/libseninputupdaterapi.so` | `0x5244` |
| `usr/lib/libupdaterapi.so` | `0x13324` |
| `usr/lib/libuudfileinputupdaterapi.so` | `0x95AC` |

Offsets refer to library files, not partitions. [The implementation](../../a7m4/patching.py) resolves the ELF dynamic symbol, maps it through an executable PT_LOAD segment and verifies the entire original function against the [SHA-256 allowlist](../../a7m4/profiles/updater.json). Unknown implementations are refused.

The reviewed official public-key DER SHA-256 is `be79b3323d7d92dff52175fc6d12825d73cfc68c32e4fcbca5c7d36fc04bdf10`. This identifies the reviewed base; it is not the SHA-1 value used by the check above.

## Procedure

Complete [setup](../../docs/setup.en.md), [custom cable preparation](../../docs/wiring.en.md) and your own complete backup first. Generate an independent key or deliberately choose the published research identity:

```powershell
python -m a7m4.offline keygen local/my-keys
# Offline only, using your original unmodified updater backup
python -m a7m4.offline unlock local/my-backup/nflasha1.bin --public-key local/my-keys/updater-public.pem --output output/nflasha1-custom.bin
```

The builder traverses bounded FAT chains, verifies initrd MD5 against `p1chksum`, preserves TAR/POSIX metadata, changes one PEM and four libraries, rebuilds SquashFS, and re-extracts it to compare every logical entry and metadata field. It updates `p1chksum` and retains partition size and allocation. Unknown formats or insufficient allocation are refused; FAT is not reformatted.

For installation through the same builder:

```powershell
python -m a7m4 maintain --action unlock
```

This first completes a fresh full backup, then asks for a **public key** path, prepares a per-camera plan, requires exact confirmation, writes only `nflasha1` and verifies the complete readback. The corresponding BAT is `advanced/刷入验签跳过版更新器.bat`. The private key is never installed in initrd or sent to the camera.

## Maintainer's published existing pair

[keys/published](../../keys/published/README.md) contains the owner's previously used pair, explicitly authorized for publication.

- Public PEM file SHA-256: `c39f3d878e129bbac87ad346182df754d7dd99d80c35c38bbb6517e37ca8e449`.
- Public DER SHA-256: `eed3fd52e3adc60ef13b584bc0b50345ee96639be81efa02e0031a6eccc65e76`.
- RSA-2048, exponent 65537.

**The private key is public: anyone can impersonate this signing identity.** A successful signature cannot establish publisher identity. Review package sources and contents yourself. Keep newly generated private keys in ignored local storage and offline backups.

## DAT signing and packaging

Re-sign an already correctly packed UFU/DAT:

```powershell
python -m a7m4.offline resign local/prepared.DAT --private-key keys/published/A7M4_updater_private.pem --output output/BODYDATA.DAT
```

The signer bounds-checks UFU big-endian length/tag chunks, locates FDAT's final 16-byte IV and 256-byte signature, signs SHA-256 of `FDAT ciphertext || IV` with PKCS#1 v1.5, recomputes CRC32 over all bytes preceding DEND and verifies the new signature. It does not print key contents.

Re-signing does not repair internal firmware. Modified plaintext needs updated image checksum manifests, UDTRFIRM header CRC, 1024-byte UFU block sums and correct AES re-encryption. [firmware.py](../../a7m4/firmware.py) provides the independent implementation. Re-signing an original package cannot bootstrap trust on an unmodified updater.

## Restoration and validation limits

Use `python -m a7m4 maintain --action restore_official` with a **complete pre-modification backup from the same camera and firmware base**. The host verifies content binding and logical files/metadata beyond the permitted PEM/entry changes, refusing unrelated firmware versions.

Historical custom 6.04/6.05 installations and user feedback support the underlying trust modification on the maintainer's camera. The extracted host has only offline validation so far. Other baselines, all update channels and whether later official updates overwrite trust configuration require fresh checks.
