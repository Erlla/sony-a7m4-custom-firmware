# Fit your own M4 look with an AI Agent

[中文](AGENT_TRAINING.md) · [Training results](README.en.md) · [Camera JSON contract](../../methods/08-custom-lut/FORMAT.md)

Provide original ARW files and the desired output from each same RAW. An AI Agent with local file access, coding tools and Python execution can adapt the existing workflow and fit a camera-native look JSON. The deliverable is a look file plus reproducible evaluation records; a desktop application or turnkey training package is not required.

**The execution environment still needs the adapted M4 model, response weights, native codec and development runtime.** Those dependencies and the complete research training workspace are not distributed with this documentation. An Agent given only the public results can organize the dataset and identify missing dependencies; it must not claim to have run the M4 model without them.

## Instructions to give your Agent

> Follow this guide to fit my look using the existing M4 model. Read the available workspace handoff and current model contract, then locate existing tools and dependencies. My dataset contains original ARWs, targets developed from those same ARWs, and optional original camera JPEGs and development settings. Ordinary photographs are acceptable; I do not have a professional chart. Perform pairing, scene grouping, region sampling, parameter search, integer quantization, production-renderer verification and delivery. Freeze the M4 response model initially and optimize the look grid, protecting skin, shadows and color continuity. Do not add PC lens correction. Ask together only for genuinely missing files, pairing information or target settings. Distinguish predictions from physical camera results and preserve scripts, manifests, configurations and records for continuation. Do not require camera import and recapture for every optimization round.

## Separate the tasks

| Task | Input and output | Treatment here |
|---|---|---|
| Calibrate the M4 response | Known-parameter ARW/camera-JPEG pairs → camera response model | Reuse the existing calibration; each user need not recapture probes |
| Fit a look | ARW + desired target + M4 model → native look JSON | Main task of this guide |
| Validate in camera | Candidate JSON + representative fresh captures → physical result | A small final batch, rather than every search iteration |

Do not retrain the camera-response network for each new look. An ordinary RGB post-processing map is not automatically a camera-native parameter file.

## Required inputs

| Input | Requirement | What the Agent checks |
|---|---|---|
| Model and runtime | Required before execution; supplied once by the maintainer | Model contract and recursive dependencies, development operators, response weights, native codec, Python/CUDA environment |
| Valid M4 native seed JSON | Required; the maintainer may supply it | Camera format, Gamma/matrices/base coefficients, grid, defaults and supported context |
| Original ARW | Required | Camera and RAW format, WB, ISO, exposure, dimensions and native records; preserve the original |
| Same-RAW target image | Required for direct image fitting | Prefer original-size 16-bit sRGB TIFF; establish color space, orientation, crop and target recipe |
| Original camera JPEG from that exposure | Recommended | Check model reproduction only when the actual look, LUT and adjustments are known |
| Development recipe/settings | Must be known; sidecar file optional | Software/version, look, WB, exposure compensation and output space; record explicit user confirmation if no sidecar is available |
| DCP, cube or preset source | Preserve when available | Required input domain, base development and software settings; extension alone does not establish equivalent conversion |

Targets may represent the user's grading or a specified software look. To reproduce this project's Fujifilm targets, use the same Sony ARW converted to RAF and developed in **RAW FILE CONVERTER EX**. Do not silently substitute Lightroom+DCP. This reproduces that software chain, not a physical Fujifilm-camera ground truth.

A reproducible target recipe can be applied to existing calibration RAWs, and multiple looks can share the same RAW set. New captures are not required for every style. JPEG targets can support trial fitting after appropriate image loading and color management; disclose compression and bit-depth limitations. Unpaired inspiration images are style references, not paired numerical truth.

## Use ordinary photographs

A professional chart is optional. Include skin, vegetation, sky, blue objects, white and dark materials, and smooth brightness transitions. Cover the exposure and WB conditions the user actually wants. A starting suggestion is 15–25 training/development pairs plus 3–5 genuinely unseen scenes; these are engineering suggestions, not fixed program requirements. A smaller set can produce a scene-limited trial.

Group exports of the same RAW, burst frames and scene crops together. Split **scenes** into training, development and final test before sampling pixels. Randomly splitting pixels from one scene is not independent validation. If final-test results influence further tuning, relabel them as development/regression data and retain new test scenes.

Build actual corresponding regions and semantic labels for each image: flat colors, skin, skin shadows, white, blue, deep shadows and gradients. Exclude misaligned edges, occlusions and uninformative fully clipped pixels from appropriate color losses, while reporting clipping counts and retaining representative shadow/highlight evaluations. Do not copy historical chart coordinates or skin labels.

Natural scenes also need corresponding-pixel and gradient checks; a few large ROI averages can hide local errors. RGB histograms are supplementary and cannot replace spatial color correspondence.

## Write a task manifest

The Agent maintains a task manifest in a new case directory. The example below is a **documentation convention, not an existing CLI or model input schema**. Adapt it to the actual implementation. Resolve paths relative to the manifest; these sample filenames do not imply files already exist.

```json
{
  "schema": "agent-look-task/1",
  "goal": "Fit my look into the supported M4 native JSON format",
  "camera": "ILCE-7M4",
  "model_contract": "model/forward_model.json",
  "seed_look": "seed/base.json",
  "target_recipe": "recipe.md",
  "policy": {
    "fit": "grid-first",
    "freeze_camera_model": true,
    "pc_lens_correction": false,
    "exposure_or_WB_normalization": false
  },
  "pairs": [
    {
      "id": "scene01_frame01",
      "scene_group": "scene01",
      "role": "train",
      "raw": "raw/scene01.ARW",
      "target": "targets/scene01.tif",
      "camera_jpeg": "camera/scene01.JPG",
      "regions": "regions/scene01.json"
    },
    {
      "id": "scene02_frame01",
      "scene_group": "scene02",
      "role": "development",
      "raw": "raw/scene02.ARW",
      "target": "targets/scene02.tif",
      "regions": "regions/scene02.json"
    },
    {
      "id": "scene03_frame01",
      "scene_group": "scene03",
      "role": "test",
      "raw": "raw/scene03.ARW",
      "target": "targets/scene03.tif",
      "regions": "regions/scene03.json"
    }
  ]
}
```

After inspecting the originals, record file identities, actual capture/development settings, sampling units, dependency versions and run configuration. The Agent should create the manifest and region adapter; users need not hand-author JSON or annotate every region manually.

## Execute in order

### 1. Inspect the model and execution scope

Read the available workspace handoff, model contract and dependencies. Identify the backend from the actual contract rather than historical README defaults. The explicit route is:

`ARW CFA → explicit Sony Edit native frontend → M4 zero-grid bridge → calibrated signed7 grid response → output`

The grid stage remains partly empirical; this is not a bit-exact reconstruction of the entire hardware ISP. Photo Gamma, matrix endpoints, WB and menu-state coverage have limits. Report a concrete unsupported state rather than silently treating it as supported.

Before training, locate the model, actual weights/operators, codec, seed and at least one valid pair. If dependencies are missing, report them without fabricating scores.

### 2. Establish pairing, color space and geometry

Pair by actual RAW origin, not merely similar filenames. Check dimensions, orientation, color space and development settings. Record exposure and WB per group; groups may differ. Do not normalize every group to one exposure or WB and thereby change the target.

Do not add PC lens correction. Preserve the recorded historical state of any camera compensation. If development changed geometry, establish coordinate maps or common valid regions before comparison. Geometric registration must not include color correction, exposure/WB matching or histogram matching.

Each usable pair must have a source relationship, scene group, role and actual region mapping. Record exclusions with their reasons.

### 3. Measure the seed before optimization

Measure model output against the desired target. Separately, when known native settings and original camera JPEGs are available, measure model reproduction of those camera outputs. Do not subtract or conflate these two errors.

Inspect a full render and local crops before scaling up. Verify units, channels, sampling and shadow direction. Bind caches to RAW, model/implementation, native parameters and geometry. Changing matrices, Gamma or base coefficients invalidates the relevant native cache; grid-only changes may reuse an unchanged frontend. An old `complete=true` record is not proof that a new task has run.

### 4. Freeze the camera model and fit the look

Initially retain the seed's Gamma, matrices, base coefficients, WB deltas and menu defaults. Optimize **3×5×9×9 = 1,215 grid integers**, bounded to **−64…63**. A ±16 trust radius around the seed is a reasonable starting point; expand only within calibrated coverage. Photo/live grids can follow the existing synchronization policy, while retaining their separately encoded native parameter blocks.

Combine corresponding-region/pixel ΔE00 with a tail loss, shadow/skin-shadow/white-material penalties, color-path and gray-axis continuity protection, and small parameter-deviation/local-change regularization. Record weights and units. As an implementation starting point, the current grid search uses two Adam rounds of 1,800 steps, worst-20% error emphasis and an integer-forward/STE final phase; these are not guaranteed accuracy settings.

Use the development set to select starts, steps and weights. Screen actual integer candidates, not just floating-point tensors. Only expand into joint Gamma/matrix/base-coefficient search when supported operators and response data justify it; recompute affected native stages and separately measure continuous, constrained and quantized losses. More dimensions are not proof that those searches were actually executed.

### 5. Apply guards and verify the exported file

Protect development scenes, shadows, skin shadows and continuity while improving the desired match. Existing reference tolerances allow a group mean increase of 0.015, P95 of 0.04 and maximum of 0.08; each condition mean may rise by at most `max(0.05, baseline condition mean × 2%)`. These are small baseline-relative allowances, not a promise that every region improves or that maximum ΔE00 is below 3.

Record the actual guards before selection. Do not relax them after a failed candidate to manufacture a pass. If more targets enter the gradient, update their roles. Retain the seed if no verified improvement passes, and report the principal residuals.

Encode integer parameters using the actual camera format, seal runtime identity, validate and compile. **Reload the exported JSON**, then use the production forward/output path, including clipping and rounding, for fitting/development samples and final unseen scenes. In a grid-only search, verify that other native parameters did not accidentally change. File validity, offline improvement and physical camera acceptance are separate conclusions.

### 6. Deliver a resumable task

Deliver a plain folder with original-style-name look JSONs, usage instructions and evaluation entry points. Preserve the task manifest, adapter scripts, real commands, configuration, seed identities, dependency identities, logs and evaluation records. Keep source images, targets, caches and weights in agreed local data locations.

For train/development/final test separately, report mean ΔE00, P95, maximum and RGB RMSE, stating pixel-versus-ROI-mean sampling and weighting. Identify 0–255 RGB units when used. Include shadow, skin-shadow, white-material and per-scene residuals, RGB distributions, representative full images, shadow crops and gradients. ROI-mean RMSE is not full-image pixel RMSE, and averaging per-image P95 does not yield pooled P95.

Offline-verified candidates may be delivered as such. If physical verification is needed, prepare one small representative batch with a baseline comparison; do not insert recapture into every optimization round or claim camera acceptance before capture.

## Connect to an actual implementation

The public repository supplies the [camera JSON contract](../../methods/08-custom-lut/FORMAT.md), [firmware implementation notes](../../methods/08-custom-lut/IMPLEMENTATION.md) and [evaluation results](README.en.md). It does not distribute the complete M4 training workspace, weights, Sony constants or runtime. Obtain the required accessible dependencies from the maintainer or user before execution.

| Capability | Contract the Agent must establish |
|---|---|
| RAW/native frontend | Supported camera/RAW format; actual WB and ISO; explicit Gamma, endpoints and menu context |
| Frozen M4 response | Known input domain, signed7 layout/range; identical model/version for training and rendering |
| Pixel correspondence | Actual regions, masks, geometry and color space; ordinary scenes, not only fixed charts |
| Solver | Gradients or numerical search over look parameters using current scene roles and losses |
| JSON encoder/compiler | Actual format validation and canonical runtime hash; exported-file reload |
| Production render/evaluation | Actual exported parameters, clipping and rounding; final unseen-scene results |

In the maintainer's research workspace, useful implementation names include `edit_explicit.py`, `explicit_training_data.py`, `explicit_grid_fit.py`, `run_refinement.py`, `export_candidates.py` and `replay_candidates.py`. These are discovery hints, **not source links guaranteed to exist in this public repository or a generic CLI**.

Write a thin adapter in a new case with explicit model, seed, samples, regions, scene roles and outputs. Historical `CASE/PRIOR`, `prepare()`, `Operator`, P01–P21 splits and fixed fifteen-look packaging require adaptation. Do not overwrite old cases or production models to satisfy hardcoded paths. Preserve real runnable commands rather than inventing an unavailable `train --dataset` interface.

Photo/live native parameter blocks are separately encoded: **do not copy photo Gamma/coefficients directly into live parameters**. Synchronizing a fitted grid does not imply identical complete pipelines. Use the codec's actual capability declarations and layout.

If using ROI atlases, preserve the actual neighborhood required by spatial operators and compare representative regions against full-image rendering. Historical 12-pixel halos, 1400×933 coordinates and fixed atlas width are not universal geometry contracts.

## Engineering pitfalls

- `material_torch.lab` accepts RGB in 0–255; other Lab functions may expect 0–1. Check units before reusing losses.
- Nonlinear rendering of a region average does not equal averaging rendered pixels. Preserve pixels or use renderer-equivalent node aggregation.
- R5 reference grids may contain large neighboring changes. Do not blindly project them to adjacent differences ≤4; protect output continuity and relative changes.
- The camera grid has 1,215 entries. A renderer's `129³` acceleration table is not the camera grid size.
- Three PyTorch processes exhausted commit memory on a historical 32 GiB host despite free VRAM. Begin serially and budget both host memory and VRAM; that host's two-process limit is not a universal limit.
- On Windows, use an actual process-status API rather than `os.kill(pid, 0)` to query liveness.
- Natural-scene ΔE00 measures agreement with the supplied target; do not call it certified absolute color accuracy.
- User images, TIFFs, weights, Sony constants and look JSONs are not automatically committed to Git/LFS. Public methods do not imply public distribution of dependencies.

## Evidence and references

- [Twelve-look evaluation and limitations](README.en.md): the source of these engineering starting points; historical regression data do not promise new-user unseen-scene accuracy.
- [Camera JSON format and conversion boundary](../../methods/08-custom-lut/FORMAT.md).
- [LUT operation and camera interface](../../methods/08-custom-lut/README.en.md).
- [751K/sony-look-bridge](https://github.com/751K/sony-look-bridge): explicit Sony Edit operator reference.
- [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware): native-parameter and fitting research; not M4 hardware-response ground truth.

This is an Agent-executable method description, not a complete training-software distribution. It includes no private dependencies or look parameter files and makes no claim that a new user's data have already been trained. The Agent task manifest and the camera-import JSON are different formats.
