# LUT training methods, models and dense RAW chart

[中文](README.md) · [Agent execution guide](../docs/custom-lut-training/AGENT_TRAINING.en.md) · [M4 model](MODEL.en.md) · [Dataset](DATASETS.en.md)

An AI Agent uses the frozen M4 computer model, the same RAW input and paired target colours to search native camera parameters and export a JSON look for the custom LUT menu. Within the model's qualified scope, iterations run on the computer without importing each candidate into the camera and photographing again.

Colour LUTs from different sources and global grading recipes can supply targets. Apply the desired look to the supplied Sony chart and export a TIFF for fitting. The twelve bundled Fujifilm targets provide ready-made examples.

This directory contains research code and composable command entry points. It is intended for an Agent to read and adapt, with no desktop training application. Frozen model files, dense-chart RAWs and target samples are separate training assets, outside source history. Users obtain Sony reference files themselves.

## Prerequisites

| Item | Source |
|---|---|
| Training and third-party source | This repository; retain third-party licence texts |
| Frozen models and chart assets | Separate training asset attachment in project [Releases](https://github.com/Erlla/sony-a7m4-custom-firmware/releases); identities in [Model](MODEL.en.md) and [Dataset](DATASETS.en.md) |
| Sony reference files | Supported macOS Edit universal binary and `srsettings0000.tbl`, obtained separately; only constants are read on Windows |
| Starting native look | A valid M4 JSON; finished look packs remain separate Release downloads |
| Target style | Same-RAW target TIFFs or an explicit target-generation recipe; assets also contain existing target samples for twelve Fujifilm simulations |

## Environment and commands

The preparation was verified on Windows x64 with Python 3.12. Install `requirements.txt` and select an appropriate CPU/CUDA PyTorch build using its official instructions. Formal CUDA RGB16 replay additionally requires CUDA Toolkit/NVRTC; CPU can be selected explicitly. These tools neither install camera drivers nor access USB.

```powershell
python -m pip install -r training/requirements.txt
$assets = 'D:\M4-training-assets'
$edit = 'D:\Sony-reference\Edit'
$sr = 'D:\Sony-reference\srsettings0000.tbl'
python training/run.py doctor --assets $assets --sony-edit $edit --srsettings $sr
python training/run.py render-chart --assets $assets --sony-edit $edit --srsettings $sr `
  --native 'D:\looks\my-look.json' --target-tiff 'D:\targets\my-look.tif' --output 'D:\runs\baseline'
python training/run.py render --assets $assets --sony-edit $edit --srsettings $sr `
  --raw 'D:\photos\scene.ARW' --native 'D:\looks\my-look.json' --output 'D:\runs\scene'
```

## Apply a LUT and fit your own look

1. Open `charts/SONY-v4.5-100MP-5300K.ARW` in an editor that supports this synthetic RAW.
2. Fix the development profile, as-shot WB and exposure settings. Disable automatic grading, lens geometry correction and local effects. Set the input colour space and transfer curve required by the LUT, then apply it or your global grading recipe. The editor's base development contributes to the target appearance.
3. Convert to sRGB and export a flattened **16-bit RGB TIFF, 11648×8736, with the original orientation and tile layout**, embedding sRGB ICC. Uncompressed, ZIP and LZW exports are supported. Preserve the 32×32 tile positions and check effective RAW cropping. See [target requirements](DATASETS.en.md).
4. Give the TIFF and recipe to the Agent, score the starting look, then fit it using the command below.

`fit-chart` optimises the grid with the frozen M4 model and formally replays the exported integer JSON. Custom TIFF fitting assigns a new look ID so the candidate can coexist with the seed.

```powershell
python training/run.py fit-chart --assets $assets --sony-edit $edit --srsettings $sr `
  --native 'D:\looks\my-look.json' --target-tiff 'D:\targets\my-look.tif' --name 'My look' `
  --target-notes 'Global LUT, matching input space, as-shot WB, exposure 0, sRGB export' `
  --qualification aggregate --steps 1800 --trust 16 --output 'D:\runs\my-look-proposal'
```

Record the actual editor, LUT, input space, WB and exposure in `--target-notes`. For an untagged TIFF, `--assume-srgb` records your confirmation that the exported pixels are sRGB. Convert files carrying another ICC profile in the editor before export.

| Output | Contents |
|---|---|
| `candidate.json` | Parsed and compiled look candidate |
| `target.json` | Target identity, colour space, sampling and recipe notes |
| `fit.json` | Before/after scores, optimisation history, chart gate and local regressions |
| `paired_outputs.npz` | All chart targets, baseline/candidate colours and per-colour errors |
| `receipt.json` | Input, target, model and result record |

`--qualification aggregate` requires a lower mean ΔE00 and P95 no higher than the baseline plus 1e-4. It reports the number of regressed colours, largest per-colour regression and overall maximum error, allowing trade-offs when fitting a new style. The default `per-colour` policy requires a lower mean and every colour within its baseline error plus 1e-4. Keep the chosen references fixed during the run.

`chart_candidate_qualified` reports the selected chart gate. The Agent uses paired photographs and gradient checks from the [guide](../docs/custom-lut-training/AGENT_TRAINING.en.md) to decide adoption. `candidate_accepted` stays `false`, and physical-camera results are recorded separately.

Bundled targets remain accessible with `--film CC` and other keys, mutually exclusive with `--target-tiff`. Omitting both retains CC. Custom TIFF fitting uses the shared model, Sony inputs and your target image.

Global hue, saturation, curves and colour mappings suit this workflow. Grain, soft focus, local masks and subject-aware effects require spatial or scene information beyond uniform colour tiles. Reproduction depends on camera parameter capacity, model coverage and target gamut.

## Method

1. Freeze the camera model, inputs, targets and WB/exposure settings; score the starting look.
2. Start with the 1215 integer grid values (`3×5×9×9`, `−64…63`), keeping photo/live branches consistent.
3. Evaluate ΔE00, tail errors, neutral shadows, skin shadows and continuity; use RGB histograms as diagnostics.
4. When grid-only fitting stalls, measure native Gamma/matrix/base-coefficient responses and use joint signed-integer proposals. The source includes 116 selected native directions and a MILP solver primitive.
5. Reload the exported JSON and rescore through the formal `129³` table and RGB16 kernel, including all protected data, before adoption.

`response_network.py` is the frozen camera response, not a network to retrain for each look. `fit_grid.py` changes filter parameters. `integer_search.py` only proposes changes: exact re-rendering remains required. Recompute the native frontend when native parameters change; grid-only changes can reuse an identical frontend.

The native frontend uses Sony Look Bridge's explicit Edit arithmetic followed by the calibrated M4 bridge and grid response. No running Sony application or connected camera is required. The grid stage remains empirical M4 calibration, rather than a proven bit-exact reconstruction of the complete BIONZ hardware pipeline. New looks can normally reuse existing RAWs, targets and models; new bodies or unqualified ISO/WB/menu/native contexts require additional coverage evidence. Final camera checks can be grouped after offline optimisation.

Special thanks to **Hearts-Ace**, author of [sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware), for substantial support with the training methodology and research into native parameters, grid optimisation and dense synthetic charts. Thanks also to [751K/sony-look-bridge](https://github.com/751K/sony-look-bridge) for native rendering research and its MIT implementation. See [third-party notices](../THIRD_PARTY_NOTICES.md).
