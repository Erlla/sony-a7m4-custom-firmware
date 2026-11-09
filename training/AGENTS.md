# Instructions for a training Agent

Read README, MODEL, DATASETS and docs/custom-lut-training/AGENT_TRAINING before using this directory. The camera-response weights are frozen; train a new filter by changing native JSON, not by changing the camera model to imitate that target.

- Start by resolving the model/asset manifest and locally supplied Sony dependencies. `doctor` must succeed before claiming a model render. Do not substitute unrelated RAWs, targets or weights.
- The dense chart's input is SONY-v4.5-100MP-5300K.ARW (SHA-256 begins 45455a7c), not RAF, design RGB or an old chart. RAF serves target export. The cached front values were derived from actual ARW CFA/metadata; preserve their file identity.
- The chart is one synthetic input with 99,372 colour tiles, not 99,372 independent scenes. Keep same-RAW exports/related crops together when assigning training/development/test roles.
- Do not add lens correction, exposure normalisation, white-balance matching, histogram matching or target smoothing. Historical camera lens compensation is a separate captured fact.
- CC's controlled as-shot target differs from its older manual Tint23 target. The other eleven historical targets are not independently WB-verified. Preserve this distinction rather than silently replacing targets to improve a score.
- `fit_grid.propose` and `integer_search.solve` produce proposals only. Reload/compile actual integer JSON and evaluate with `CameraModel.bake` (129 cubed, 32768 chunks) plus `sample`. Keep the frozen camera model and original native fields fixed during grid-only fitting.
- Establish fixed per-colour and aggregate reference floors. The latest strict method permits one epsilon of 1e-4 outside the reference; never accumulate it across rounds. A failed formal gate retains the previous look.
- Protect shadow a*/b*/chroma and skin-shadow colours against their paired targets, not an invented neutral/warm appearance. Preserve intended style chroma. Report hue-valid masks and Gamma monotonicity explicitly; do not force all film curves to be globally concave.
- The 116 selected native axes tie endpoint/context changes together; they are not every independent camera parameter. Changing Gamma/matrices/coefficients invalidates native caches and requires native re-rendering. Do not reuse RGB from the old native look.
- Existing CLI chart fitting lacks the user's new real-scene guards until you add paired scenes. Mark it as a chart candidate; never claim all-scene or physical-camera acceptance from chart loss alone.
- Keep raw data, output arrays, models, generated JSONs and images out of Git. Do not use camera-control tools or publish results without the user's instruction.
