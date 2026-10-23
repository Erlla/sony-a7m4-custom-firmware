# 6.62 combined LUT / aspect-ratio / sound recipe

[Independent re-audit, 2026-10-23](REVIEW-20261023.md): no new defect confirmed. The isolated pool-reuse hypothesis was withdrawn after checking the native outer mutex. New layout, shared-state and locking checks passed; firmware hashes are unchanged. Camera results obtained later are described below.

This publishes authored CP adapter sources and an exact-layout, offline component composer. It merges the accepted standalone T22 aspect implementation into the newer LUT/sound baseline. The package passed offline checks and subsequent single-camera A–J and menu/sound functional tests. Cropped JPEG pixels were correct, but their EXIF width/height remained stale. A [6.63 EXIF correction](../jpeg-exif-663/README.md) is now offline-verified and awaits camera regression. **LUT P2 remains open**.

See [the detailed integration notes](README.md), [input/output identities](layout.json), and [validation summary](validation.json). Run the tool from this source checkout after installing `.[firmware,test]`:

```text
python -m a7m4.combined662 --help
python -m pytest -q
```

The `cp`, `ap`, and `string` commands require exact privately held input images, verified by SHA-256. CP compilation also pins the compiler. Outputs must be new files. There is no device access, signing, flashing, or standalone DAT build command. Complete manufacturer binaries, resources, calibration, and private research history are not included. An installed wheel without the adjacent `native/` directory is not supported for this research tool.

The changes relocate aspect CP code/BSS, preserve ARM-to-Thumb function typing, combine boot/CRC/MMU handling, chain AP constructors, append relocations after the current main additions, and move four aspect labels from sound-owned IDs `0x0200AB60..AB63` to `0x0200AB4C..AB4F`. Live string records are repacked to fit their 16-bit word offsets.

The public recipes reproduced the signed package's CP, AP, and all 68 language/orientation banks byte-for-byte. The public repository test suite passed 218 tests. The research package passed 5,444 offline checks and separate signature, full decode, partition, resource, and unchanged-region verification. These are not camera tests.

The current native LUT experiment exposes one independent FL2 reference slot at 100%. JSON import and production multi-slot fitting are unfinished. The supplied A–J photographs and user feedback support startup/playback-return LUT persistence, crop geometry, RAW extent, menu/display lifecycle, and custom sounds on this camera. No frame-by-frame timing, memory or stress measurements were supplied; stock-FL2 comparison and quantitative performance remain open.
