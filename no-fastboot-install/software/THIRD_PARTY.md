# Runtime components and acknowledgements

The no-Fastboot installation approach references [YuuLuo/a7c2-camera-tools](https://github.com/YuuLuo/a7c2-camera-tools). USB protocol research also relies on the public work listed in the repository [REFERENCES.md](../../REFERENCES.md).

Runtime components are **not vendored here**. The build consumes separately supplied, hash-locked files and retains their accompanying licenses. A project source license does not relicense manufacturer drivers or third-party binaries.

| Component | Purpose and primary source |
|---|---|
| CPython / Tcl / Tk | Isolated Python and UI runtime; [CPython](https://github.com/python/cpython) and its bundled license files |
| PyUSB / libusb-package / importlib_resources | USB access; [PyUSB](https://github.com/pyusb/pyusb), [libusb-package](https://github.com/pyocd/libusb-package) |
| Sony-PMCA-RE | Authentication constants and compatible SHA-1 helper; [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) |
| Dissect FAT / SquashFS / cstruct / util | Filesystem parsing; [Dissect](https://github.com/fox-it/dissect) |
| pyelftools | ELF validation; [pyelftools](https://github.com/eliben/pyelftools) |
| cryptography / cffi / pycparser | Existing RSA public-key format handling; [cryptography](https://github.com/pyca/cryptography), [cffi](https://github.com/python-cffi/cffi), [pycparser](https://github.com/eliben/pycparser) |
| squashfs-tools-ng | Filesystem rebuilding; [squashfs-tools-ng](https://github.com/AgentD/squashfs-tools-ng) (original GPL/LGPL terms as applicable) |
| Zig / Clang / LLVM | Per-run AArch64 compilation; [Zig](https://github.com/ziglang/zig) and included component notices |
| Reviewed WinUSB binding package | Manufacturer-signed driver setup files, supplied externally with their original terms |

Exact runtime versions and component digests are in [dependencies.json](dependencies.json). This is a dependency lock, not a list of camera backups or a firmware package. A runtime asset ZIP can be supplied locally even when no binary release is hosted on GitHub.
