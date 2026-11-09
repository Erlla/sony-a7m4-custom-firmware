# Dense RAW chart and Fujifilm targets

[中文](DATASETS.md) · [Machine-readable manifest](charts/manifest.json) · [Training](README.en.md)

The synthetic100MP carrier comes from Hearts-Ace's R5 research: **99,372** tiles,364 columns×273 rows,32 pixels per tile. It is one synthetic input, not99,372 photographs or independent scenes.

| File | Role | SHA-256 |
|---|---|---|
| `SONY-v4.5-100MP-5300K.ARW` | Required model RAW input | `45455a7c46d7aa2454e73a67c32b01a29a13739d203e54ed24592a451fd48bd6` |
| `GFX100SII-v4.5-100MP-5300K.RAF` | Same-source RFCEX target export | `fd31efd39ed671e39891984ee0f9c56933599d52764a77138c905166cbb8dcda` |
| `SONY-v4.5-100MP-5300K.DNG` | Reference carrier, not a silent ARW replacement | `0b9ea8efa0c67f7584409473d959da04716ae469441661955a8a30ab934026b1` |

Assets contain those carriers, CFA/metadata-derived Sony input arrays, design/category labels and samples for twelve Fujifilm targets. Preserve the actual ARW black levels, captured WB gains, scale, crop and SSCS mapping. Design RGB supplies labels/curve axes and is not substituted for RAW input.

Target samples are float64 means of encoded-sRGB pixels x14…18 at y16 inside each tile, in original tile order. There is no smoothing, new white point, exposure normalisation or histogram matching. `fuji_targets.npz` losslessly stores these training samples, with source TIFF identities. It does not establish full-image pixel accuracy. Complete target TIFFs are outside source history.

The directory contains `models/forward_model.json`, `models/grid_response.pt`, `models/bridge/`, `charts/dataset.json`, the three RAW carriers, `charts/sony_input.npz`, `charts/design_pairs.npz`, `charts/fuji_targets.npz` and `manifest.json`.

Targets are RFCEX3.0 powered by SILKYPIX outputs: CC, Provia, Velvia, Astia, Reala Ace, Pro Neg.Hi/Std, Classic Neg., Nostalgic Neg., Eterna, Eterna Bleach Bypass and Acros. They are not replaced with Lightroom/DCP targets. **CC uses the controlled as-shot-WB export; the other eleven retain historical exports whose WB settings have not been independently verified per style.** Keep this status and each identity rather than describing all twelve as controlled as-shot targets or claiming improvement by replacing them.

Existing target samples require no new export or photograph. New styles need targets generated from the same carrier, with an explicit recipe. Prefer16-bit sRGB, original size/orientation, exposure compensation0 and the agreed WB. Do not equate Kelvin labels across software. Add no computer lens correction.

Use the dense chart for gamut, neutral shadows and hue-versus-brightness behaviour. Reuse paired real photographs to protect materials, skin shadows, exposure and WB coverage. Ordinary paired photos work without a chart. Iterations reuse these data in the computer; no per-candidate camera shoot is required. Development/regression material used for selection is not an independent final test.
