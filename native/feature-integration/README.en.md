# LUT, aspect-ratio and sound component integration

This directory provides authored CP adapters, exact layouts and an offline AP/CP/resource composer. It is organized by implementation, not firmware release. Test builds, deployment manifests, per-run acceptance and research progress stay in the research repository.

See the [implementation](README.md), [pinned inputs/outputs](layout.json), [component checks](validation.json), and [layout/concurrency review](REVIEW.md). Input images and compilers must match their full SHA-256 values; the addresses are not portable to arbitrary firmware.

```text
python -m pip install -e ".[firmware,test]"
python -m a7m4.feature_integration --help
python -m pytest -q tests/test_feature_integration.py
```

Run from a source checkout with the adjacent `native/` directory. The `cp`, `ap`, and `string` commands write new component files only. They refuse overwrite and optimized Python, do not sign packages and never access a camera.

The implementation relocates aspect CP code/BSS, preserves ARM-to-Thumb typing, combines boot/CRC/MMU handling, chains AP constructors, appends relocations and moves aspect labels away from sound-owned resource IDs. String records are repacked to fit 16-bit word offsets. The CP, AP and all 68 language/orientation banks have been reproduced against the pinned components; native OS services are modeled, so replay does not prove camera pixels, timing or performance.

The LUT interface exposes one independent reference slot at 100%. In-camera JSON import and multi-slot fitting are unfinished. Cropped JPEG metadata requires the separate [EXIF dimension component](../jpeg-exif-dimensions/README.md). Complete firmware, private camera data, generated packages and per-version test records are not distributed here.
