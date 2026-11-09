# M4 forward model and filter-parameter fitting

[中文](MODEL.md) · [Training entry](README.en.md)

The frozen **M4 forward model** predicts how camera parameters affect output. The **filter fitter** searches those parameters. New styles reuse the camera model.

The pipeline is Sony ARW → explicit native frontend controlled by JSON → frozen M4 zero-grid bridge → frozen signed7 response → formal129³ table/RGB16 kernel → predicted output. The native frontend uses Sony Look Bridge's CFA, black/WB, ITP, SSCS, native colour/Gamma and spatial-detail arithmetic. The bridge and neural grid response come from existing M4 calibration.

## Assets and dependencies

`models/forward_model.json` in the training assets is the entry contract. Asset paths are relative; `code:` resolves inside `training/source`, and `external:` identifies locally supplied files. Preserve hashes and all bridge, anchor, codec and response dependencies. The original mathematical contract is SHA-256 `4e516ebced9075eba9a4a69a89f410606abb87434077c4ac8986ca0690968e6d`. This organisation changes paths/import boundaries while retaining frozen weights and arithmetic; it does not retrain the model.

Required Sony reference identities:

| File | SHA-256 |
|---|---|
| Supported macOS Edit universal binary, read for constants | `43ae5e1cb4bc18a52183b430e02b16a4506b89a907a6fd0feed359fa85a82ce9` |
| ARM64 slice | `c250f466835c5380d244de33a6824e9930fe3f250ce9b1d948d5e379cc4c8133` |
| `srsettings0000.tbl` | `ef1dd637b6656dc895246265bd311fbc63b0e95f7b50005ceb61c19d472d9aba` |

The matching official installer is [IE410_2603a.dmg](https://di.update.sony.net/NEX/3Kb405393d/IE410_2603a.dmg), SHA-256 `d7927efe5a4d67707b8d74b14511b39f353a5ca5cb79240554d73b3bda4707ab`. Download it locally, then extract only the reference files with7-Zip:

```powershell
python training/prepare_sony.py --package 'D:\Downloads\IE410_2603a.dmg' `
  --sevenzip 'C:\Program Files\7-Zip\7z.exe' --output 'D:\Sony-reference'
```

Pass the two actual paths printed by the script to run.py. Sony executables/constants are not redistributed here. Windows Edit.exe is not a substitute. Sony Look Bridge is pinned at `6302d69d6ecc827503c5f110579a7c579db101c7`; MIT source/licence are retained under `third_party`. On Windows, three libSystem math-library paths are patched to UCRT only in a runtime copy. No Sony application needs to run.

## Dimensions and replay

The native grid contains1215 signed7 integers (`3×5×9×9`, −64…63). The129³ computer output table is a different structure. The116 selected native directions comprise12 Gamma-shape directions,96 matrix directions and8 base-coefficient directions. Gamma contexts and matrix endpoints remain tied rather than independently fitted. The signed MILP helper proposes changes; measured responses and exact re-rendering are required.

Grid-only changes may reuse identical native RGB. Gamma/matrix/coefficient changes invalidate that cache. Formal scoring keeps129³ node order,32768 chunks, float64 bridging, float32 neural response, float64 interpolation and RGB16 quantisation. Continuous or local-surrogate scores are insufficient for adoption.

## Qualification

One historical same-RAW M4 JPEG comparison over140 patch centres measured mean ΔE00≈0.823, P95≈2.002 and RGB RMSE≈1.563/255. These measure model-versus-camera agreement, not Fujifilm style error or a new independent-scene acceptance.

The complete hardware ISP is not proven bit-exact. The grid stage remains empirical. Scope mainly covers photo Gamma context6, legacy endpoint0 or specifically measured fixed endpoints, captured WB weights and calibrated menu defaults. Arbitrary independent sliders, ISO/illuminant contexts, endpoint selection and adaptive noise/DRO behaviour are not generally qualified. Current rendering disables additional lens correction, RawNR, DRO and Marble.


Transfer checks used PyTorch 2.14.1+cpu: two frozen-response vectors,99,372 native chart points and the complete129³ table matched the original implementation. CPU/NVRTC CUDA RGB16 outputs matched exactly. A two-step parameter-gradient smoke check ran; neither the camera model nor a filter batch was retrained. CUDA PyTorch training was not rerun in this preparation.


### Reuse during iterations

`frozen_table.FrozenTable(model)` caches the zero-grid bridge once, retaining129³ nodes and32768 chunks for subsequent grids without subsampling. Copy its reused output buffer when retaining an old table. `spatial_native.native_pixels` re-renders native-changed ROIs from a decoded halo atlas: uint16 RGB14 linear data plus selection.npz withy/x/ends. Retain original ROIs and12-pixel halos; recheck support radius if spatial operators change. Post-native bridge and RAW frontend caches are distinct: never substitute old native pixels for changed Gamma/matrices.
