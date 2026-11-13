# AI Agent: fit a look with the frozen M4 model

[中文](AGENT_TRAINING.md) · [Code and assets](../../training/README.en.md) · [Model](../../training/MODEL.en.md) · [Dense chart](../../training/DATASETS.en.md) · [Camera JSON](../../methods/08-custom-lut/FORMAT.md)

Repeatedly change a native look JSON, predict its camera output in the M4 computer model and fit same-RAW target images. Within qualified coverage this does not require importing and photographing every candidate. This guide is for an Agent that can read files, adapt code and run Python, with no desktop training application required.

## Instruction to give the Agent

> Read this guide, training/AGENTS.md and the model/dataset manifests. Resolve actual files and run doctor first. Use the specified Sony ARW as the chart input; RAF is for target export. Preserve captured WB/exposure and add no computer lens correction. Freeze the M4 camera model and first fit the1215 signed7 grid integers, protecting real materials, skin shadows, neutral shadows and continuity. Measure Gamma/matrix/base-coefficient responses before extending joint search. Set paired data roles and fixed reference guards, reload the exported integer JSON and verify through formal rendering. Preserve runnable code and records. Do not request a camera shoot for each candidate; group requests only when targets or model coverage are genuinely missing.

## Separate the tasks

Camera-model calibration maps known-JSON RAW/JPEG pairs into a response model. New-style fitting reuses that frozen model to obtain native JSON from RAW/target pairs. Record model-versus-camera errors, filter-versus-target errors and physical-camera results separately. The chart establishes performance on its synthetic input.

## Inputs and pairing

Use the supplied model assets, a valid native seed and same-source targets. Existing twelve-style target samples can be reused. A new style needs same-RAW output or a reproducible target-generation recipe. Unpaired reference images are style references rather than numerical ground truth.

Users can apply colour LUTs from different sources or global recipes to the supplied Sony ARW chart in a grading application. Export a 11648×8736 RGB16 sRGB TIFF with its original orientation and layout. Score the seed using `render-chart --target-tiff`, then fit using `fit-chart --target-tiff`. Record the actual recipe in `--target-notes` and check LUT input space, base development, exposure and tile placement. Commands and export settings appear in the [training entry](../../training/README.en.md).

Perform colour-space conversion in the editor. Use `--assume-srgb` for an untagged image only after confirming its export space. Convert images carrying another ICC profile before export. A single chart can start fitting, followed by real-photo and gradient evaluation using the same recipe. Grain, local masks, soft focus and semantic selection depend on additional spatial/scene information. Describe the result within its global-colour scope.

Ordinary photos work without a professional chart. Include skin/skin shadows, blue and white materials, plants, dark materials and smooth gradients. Group same-RAW exports, bursts and related crops together. Split scene groups into training, development and final test before sampling; random pixel splitting is not unseen-scene validation.

Prefer16-bit sRGB TIFF at original size/orientation. Record actual software/style/WB/exposure/colour-space/crop. Sidecar files are optional; distinguish user-confirmed settings from independently checked settings. This project's Fujifilm targets use RFCEX, not Lightroom/DCP. Do not equate Kelvin labels across software.

CC uses the controlled as-shot target; WB in the other eleven historical exports is not independently verified per style. Preserve that status. Replacing targets or WB requires a new baseline and is not a parameter-training improvement.

## Execution

### 1. Resolve dependencies and scope

Start from this repository's training directory and separate asset attachment. `doctor` resolves weights, bridge, codecs, supported Sony reference files and upstream identity. Do not require the maintainer's private directory tree or claim model execution when dependencies are missing.

The frontend uses actual ARW CFA/black/captured-WB, ITP/SSCS, JSON-controlled native colour/Gamma/spatial processing, then the frozen M4 bridge/response and RGB16 output. No running Sony application or camera connection is needed. Scope and empirical components remain as documented in MODEL.

### 2. Establish a baseline and protection set

Record input/target/model identities, seed, recipe, scene roles, sampling units and fixed gates in an Agent-maintained task manifest. This manifest is not camera-import JSON. Measure seed error and inspect full images/shadows before search.

Geometric registration establishes correspondence only: no exposure/WB/histogram matching. Preserve original polygon pixels instead of passing large ROI means through a nonlinear model. Account for clipped/low-chroma samples explicitly rather than quietly excluding hard colours.

The chart uses five interior pixels per32px tile in fixed order and the specified Sony ARW, never design RGB substituted for sensor input. Its99,372 colours and grey/hue tracks remain one synthetic RAW.

### 3. Freeze the camera model and fit the grid

Optimise1215 signed7 grid integers, `3×5×9×9`, range−64…63, while retaining native seed parameters. A relative±16 trust region is a starting budget, not a format limit. Keep photo/live grids consistent using the existing strategy without conflating native layouts.

`fit_grid.propose` provides Adam/STE proposals and `fit-chart` demonstrates chart fitting. The1800-step default is illustrative, not an accuracy guarantee. Combine mean/tail ΔE00, shadow a*/b*/chroma, skin-shadow accuracy, continuity and parameter regularisation. Add the user's actual paired scene guards before adoption; chart-only candidates are labelled accordingly.

Choose an explicit chart policy for a new style. `--qualification aggregate` requires a lower mean ΔE00 and P95 within the baseline plus 1e-4, allows colour trade-offs and reports their count and largest regression. The default `per-colour` retains every baseline colour limit plus 1e-4 and requires a lower mean. Save the baseline and use the chosen policy throughout the search. Review actual errors and gradients before adoption under either policy. Custom TIFF candidates receive a new UUID. The Agent should explicitly manage ID/revision when making subsequent revisions of the same look.

### 4. Extend with measured native responses

`native_family.py` supplies116 selected directions:12 Gamma,96 matrix and8 base-coefficient directions, with tied contexts/endpoints. Native changes require fresh native RGB; grid-only changes may reuse an identical frontend.

Measure positive/negative one-unit responses and record unavailable directions. Build per-colour and aggregate response matrices. `integer_search.solve` provides signed MILP proposals with trust radii, step budget and actual photo/live capacity. Linear predictions remain proposals: re-render with the model, then accept/reject or remeasure.

Fix pointwise/aggregate reference floors before search, tightening only to adopted improvements. The latest strict method adds one epsilon of1e-4 outside the reference, never accumulating it each round. A zero step or failed measured direction set does not prove global infeasibility. Continuous scores are not integer JSON scores.

### 5. Export and independently replay

Reload the exported JSON using seal/encode/parse/compile_native. Formal scoring uses the129³ table,32768 chunks, established floating-point order and RGB16 kernel. A node subset or direct network estimate is proposal machinery rather than formal full-table replay.

Report mean/P95/max ΔE00 and RGB RMSE, plus shadows/skin shadows, neutral L*/a*/b*/C*, valid hue tracks and actual RGB histograms. State whether brightness means L* or HSV V. Hue uses shortest signed circular differences; disclose low-chroma, black and clipping masks.

Check Gamma derivatives against its nonuniform input axis. Film curves may be S-shaped: do not claim globally negative curvature for cosmetic reasons. Keep model, inputs and targets fixed across training and replay. Existing140-patch, multi-exposure/WB and material data can be reused as regression protection without new per-candidate shoots. Data used for selection are not blind tests. Keep the old look when fixed gates fail.

## Handoff

Deliver native JSON, model/data identities, task manifest, runnable commands, continuous/integer/formal scores and residual plots. Keep rejected proposals and reasons. Final tests use scenes untouched by fitting or selection. Store source and model attachments separately; do not automatically add photos, full TIFFs, weights, generated arrays or candidates to Git.

These are research primitives for an Agent to adapt, not a desktop product pre-adapted to every user's data. Identify specific new-scene/body/context gaps and group any necessary collection. Do not revert to requiring a physical shoot for every candidate.

Special thanks to [Hearts-Ace](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) for substantial support with the training methodology and to [751K](https://github.com/751K/sony-look-bridge) for native Sony rendering research/implementation. R5 methods/charts inform the workflow; M4 response remains its own calibration.
