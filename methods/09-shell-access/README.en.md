# Shell / SSH: network, USB and Multi UART

[中文](README.md) · [Fastboot modification methods](../../README.en.md#2-fastboot-modification-methods)

Four root-terminal access methods are documented for Sony ILCE-7M4 / A7 IV. The normal-system recipes use the verified official **6.02** ELF layouts; the ULOGIO creation routines come from official **1.05 p15**. UART uses the existing BusyBox ash in p1.

| Access | Transport and authentication | Environment | Technical recipe |
|---|---|---|---|
| Telnet | IP network, TCP 23, plaintext without a login password | Normal camera system | [ULOGIO network and USB restoration](telnet-usb.md) |
| USB shell | Sony service USB bulk, after Senser authentication | Normal camera system | [The same ULOGIO recipe](telnet-usb.md) |
| SSH / SFTP | IP network, TCP 22, public key; service account with UID/GID 0 | Normal camera system | [sshd startup and NSS account](ssh-sftp.md) |
| Multi UART | Multi cable, RP2040, Cetus bridge; 115200 8N1 | p1 updater system | [Independent UART root shell](uart.md) |

SFTP is part of SSH. Wi-Fi is an IP carrier rather than a separate shell method. Sony USB bulk does not require USB networking. Multi UART reaches the camera through the CP serial interface, even though the host talks to an RP2040 USB serial port.

The linked technical recipes are in Chinese. They describe **offline firmware integration**, component identities, modification locations, activation protocols and rollback. Use your own backups and a filesystem/ELF builder; login commands apply after the corresponding changes have been installed. See [component layouts](reference-layout.json) and [validation boundaries](validation.md).

## Choosing a method

- Use ULOGIO restoration for Telnet or USB access in the normal shooting system. Their coexistence was verified.
- Use SSH for encrypted login, a PTY and SFTP. It reuses the daemon already shipped in the normal 6.02 system.
- Use the p1/Cetus bridge for maintenance independent of normal p15 startup. Shooting is unavailable in that updater environment; removing its boot flags restores normal startup.

ULOGIO and SSH are separate p15 implementations. Their combination has not undergone integrated hardware testing; replacing an entire partition with one recipe does not retain the other. UART adds code to p1 but also changes p2 mode flags, so the whole operation is not strictly a p1-only write.

## Deployment

Follow the existing [wiring](../../docs/wiring.en.md), [setup](../../docs/setup.en.md) and [maintenance](../../advanced/) guides. Back up the camera, verify exact component identities, modify offline, preserve unrelated files and partition tails, write once, then independently read back the complete physical partition before rebooting. Resume interrupted readback rather than repeating an already completed write.

The paired payload's OEM dump offsets and sizes are hexadecimal counts of **512-byte sectors**, not byte counts. Read in chunks no larger than 16 MiB, retrieve each with `get_staged`, and compare the assembled image against the candidate. Filesystem length is not necessarily physical partition length.

Verify fresh command responses and actual identity, terminal closure/reopening and normal camera operation as applicable. A marker, TCP handshake or activation message alone is insufficient. Upstream references and redistribution boundaries are listed in the [Chinese overview](README.md#参考与归属) and the repository [third-party notices](../../THIRD_PARTY_NOTICES.md).
