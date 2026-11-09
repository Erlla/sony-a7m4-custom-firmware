# LUT training methods, models and dense RAW chart

[中文](README.md) · [Agent execution guide](../docs/custom-lut-training/AGENT_TRAINING.en.md) · [M4 model](MODEL.en.md) · [Dataset](DATASETS.en.md)

An AI Agent uses the frozen M4 computer model, the same RAW input and paired target colours to search native camera parameters and export a JSON look for the custom LUT menu. Within the model's qualified scope, iterations run on the computer without importing each candidate into the camera and photographing again.

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
  --native 'D:\looks\my-look.json' --film CC --output 'D:\runs\baseline'
python training/run.py render --assets $assets --sony-edit $edit --srsettings $sr `
  --raw 'D:\photos\scene.ARW' --native 'D:\looks\my-look.json' --output 'D:\runs\scene'
```

`fit-chart` is a grid-proposal and integer-replay primitive for the Agent. Define dataset roles, shadow/skin protection, target settings and acceptance gates first using the [guide](../docs/custom-lut-training/AGENT_TRAINING.en.md). Chart fitting alone does not establish real-scene accuracy. `candidate.json` remains a proposal; `fit.json` reports whether its checks passed.

```powershell
python training/run.py fit-chart --assets $assets --sony-edit $edit --srsettings $sr `
  --native 'D:\looks\my-look.json' --film CC --name 'My Classic Chrome' `
  --steps 1800 --trust 16 --output 'D:\runs\cc-proposal'
```

## Method

1. Freeze the camera model, inputs, targets and WB/exposure settings; score the starting look.
2. Start with the 1215 integer grid values (`3×5×9×9`, `−64…63`), keeping photo/live branches consistent.
3. Evaluate ΔE00, tail errors, neutral shadows, skin shadows and continuity; use RGB histograms as diagnostics.
4. When grid-only fitting stalls, measure native Gamma/matrix/base-coefficient responses and use joint signed-integer proposals. The source includes 116 selected native directions and a MILP solver primitive.
5. Reload the exported JSON and rescore through the formal `129³` table and RGB16 kernel, including all protected data, before adoption.

`response_network.py` is the frozen camera response, not a network to retrain for each look. `fit_grid.py` changes filter parameters. `integer_search.py` only proposes changes: exact re-rendering remains required. Recompute the native frontend when native parameters change; grid-only changes can reuse an identical frontend.

The native frontend uses Sony Look Bridge's explicit Edit arithmetic followed by the calibrated M4 bridge and grid response. No running Sony application or connected camera is required. The grid stage remains empirical M4 calibration, rather than a proven bit-exact reconstruction of the complete BIONZ hardware pipeline. New looks can normally reuse existing RAWs, targets and models; new bodies or unqualified ISO/WB/menu/native contexts require additional coverage evidence. Final camera checks can be grouped after offline optimisation.

Special thanks to **Hearts-Ace**, author of [sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware), for substantial support with the training methodology and research into native parameters, grid optimisation and dense synthetic charts. Thanks also to [751K/sony-look-bridge](https://github.com/751K/sony-look-bridge) for native rendering research and its MIT implementation. See [third-party notices](../THIRD_PARTY_NOTICES.md).
