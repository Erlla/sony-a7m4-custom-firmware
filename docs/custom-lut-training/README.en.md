# Selected custom looks: training results

[中文](README.md) · [Custom LUT operation](../../methods/08-custom-lut/README.en.md) · [Scores CSV](scores.csv) · [Machine-readable results](results.json) · [AI Agent training method](AGENT_TRAINING.en.md)

To fit your own look, give an AI Agent the [execution guide](AGENT_TRAINING.en.md) and same-RAW target pairs. Ordinary photographs are supported; a professional chart is optional. Model dependencies must be supplied separately.

Twelve Fujifilm-style looks were refined through the M4 computer model. The equally weighted mean of their average ΔE00 scores fell from **2.014 to 1.190, a 40.9% reduction**. Shadow and face/neck-shadow means improved for every look. This is the offline evaluation dated 2026-11-08; **the new parameters have not yet been validated in fresh camera captures**.

This update publishes results and diagnostic plots only. The maintainer will provide look JSON files separately through [Releases](https://github.com/Erlla/sony-a7m4-custom-firmware/releases). Ricoh Positive, Ricoh Negative and Portra400NB were excluded from this optimization.

## Per-look scores

Each look uses 20 conditions and 2,194 ROI means: 42 existing RAW files provide 240 look/condition target pairs, covering exposure, three light/WB settings, ISO and materials. ΔE00 uses sRGB→D65 CIELAB, kL=kC=kH=1. RGB RMSE is across ROI mean RGB values in 0–255 units.

| Look | Mean ΔE00 | P95 | Maximum ΔE00 | RGB ROI-mean RMSE |
|---|---:|---:|---:|---:|
| CLASSIC CHROME | 1.881 → 1.228 | 4.192 → 2.913 | 10.975 → 7.132 | 3.470 → 2.571 |
| PROVIA | 1.900 → 1.048 | 4.887 → 2.829 | 13.512 → 8.998 | 5.288 → 3.318 |
| Velvia | 2.559 → 1.215 | 6.306 → 3.302 | 19.063 → 11.888 | 6.872 → 4.907 |
| ASTIA | 1.918 → 1.122 | 4.548 → 2.711 | 11.972 → 9.226 | 4.826 → 3.095 |
| REALA ACE | 2.894 → 2.152 | 7.478 → 5.703 | 15.095 → 10.557 | 6.626 → 4.767 |
| PRO Neg. Hi | 1.777 → 0.953 | 4.384 → 2.466 | 13.820 → 8.942 | 4.186 → 2.629 |
| PRO Neg. Std | 2.152 → 1.426 | 6.011 → 3.977 | 10.371 → 7.156 | 4.493 → 2.864 |
| CLASSIC Neg. | 1.750 → 1.011 | 4.640 → 2.488 | 13.087 → 12.523 | 3.608 → 2.628 |
| NOSTALGIC Neg. | 2.487 → 1.523 | 6.026 → 3.459 | 11.453 → 7.799 | 6.836 → 3.846 |
| ETERNA | 1.811 → 1.046 | 4.331 → 2.474 | 9.203 → 6.675 | 2.712 → 1.993 |
| ETERNA BLEACH BYPASS | 1.447 → 0.842 | 3.600 → 2.035 | 9.885 → 7.760 | 2.492 → 1.709 |
| ACROS | 1.589 → 0.715 | 5.619 → 2.027 | 13.824 → 7.652 | 7.043 → 2.307 |

![Twelve-look scores](images/scores.png)

## Shadows and regression conditions

| Look | Shadow mean | Face/neck-shadow mean | Seven-condition mean |
|---|---:|---:|---:|
| CLASSIC CHROME | 1.733 → 1.075 | 1.713 → 0.720 | 1.919 → 1.283 |
| PROVIA | 1.445 → 0.721 | 1.393 → 0.422 | 2.249 → 1.248 |
| Velvia | 2.062 → 0.914 | 2.384 → 0.487 | 2.971 → 1.497 |
| ASTIA | 1.544 → 0.886 | 1.446 → 0.604 | 2.202 → 1.262 |
| REALA ACE | 2.018 → 1.539 | 1.126 → 0.967 | 3.350 → 2.288 |
| PRO Neg. Hi | 1.436 → 0.664 | 1.930 → 0.366 | 2.028 → 1.115 |
| PRO Neg. Std | 1.246 → 0.899 | 1.056 → 0.610 | 2.476 → 1.419 |
| CLASSIC Neg. | 1.323 → 0.792 | 1.509 → 0.415 | 2.020 → 1.265 |
| NOSTALGIC Neg. | 1.906 → 1.279 | 1.354 → 0.577 | 2.734 → 1.597 |
| ETERNA | 1.635 → 0.838 | 1.405 → 0.402 | 1.780 → 1.128 |
| ETERNA BLEACH BYPASS | 1.141 → 0.666 | 1.132 → 0.495 | 1.578 → 0.976 |
| ACROS | 0.655 → 0.347 | 2.155 → 0.522 | 2.000 → 0.926 |

The first pass fits 13 conditions and uses seven historical conditions for candidate selection. The second pass for REALA ACE, PRO Neg. Std and NOSTALGIC Neg. directly includes those targets in constraint optimization. All data were previously observed; these are not blind-test scores. Acceptance permits small individual regressions: 0.015 in group means, 0.04 in P95 and 0.08 in maxima; those limits were retained.

## RGB distributions

These use all original chart-interior pixels at 6500K/EV0, weighted equally per ROI. Pale lines show selected baselines, solid lines the refined integer JSON, and black dashed lines the Fuji-software targets. The actual RGB16 CUDA renderer produced the pixels; distribution distances match the full evaluation receipts.

[CLASSIC CHROME](images/CC_RGB.png) · [PROVIA](images/PROVIA_RGB.png) · [Velvia](images/VELVIA_RGB.png) · [ASTIA](images/ASTIA_RGB.png) · [REALA ACE](images/REALA_ACE_RGB.png) · [PRO Neg. Hi](images/PRO_NEG_HI_RGB.png) · [PRO Neg. Std](images/PRO_NEG_STD_RGB.png) · [CLASSIC Neg.](images/CLASSIC_NEG_RGB.png) · [NOSTALGIC Neg.](images/NOSTALGIC_NEG_RGB.png) · [ETERNA](images/ETERNA_RGB.png) · [ETERNA BLEACH BYPASS](images/ETERNA_BLEACH_BYPASS_RGB.png) · [ACROS](images/ACROS_RGB.png)

![CC RGB distributions](images/CC_RGB.png)

## Method and scope

- Same-source Sony ARWs were converted to RAF and developed with the matching film simulation in Fujifilm RAW FILE CONVERTER EX, exporting 16-bit sRGB TIFF. These are software-pipeline targets, not side-by-side physical Fujifilm camera captures.
- The actual selected collection supplies the starting parameters: eight adapted R5 references and four project-derived looks. Explicit Edit operators form the native frontend; a V4 zero-grid bridge and a frozen, measured neural response model handle the color grid. Response-network weights were not retrained in this run.
- Optimization changes 1,215 signed7 grid values (3×5×9×9, −64…63, within ±16 of the starting point). Gamma, matrices, base coefficients and menu defaults remain fixed, with identical photo/preview grids. Two 1,800-step starts are followed, for three rejected looks, by two 1,200-step constrained starts.
- All original ROI pixels are aggregated at the actual 129³ renderer-LUT nodes. A 12-pixel-halo atlas matched 3,200,072 full-render pixels exactly. Reloaded integer JSONs were replayed through the real kernel over 799,536,917 ROI pixels; the largest score difference from optimization was 1.83×10⁻⁵.
- No additional lens correction or exposure/WB normalization was applied on the computer. Original capture settings remain unchanged.

## Model versus historical camera output

Twelve RAW/JPEG pairs outside this fitting set compare the original selected looks at 140 chart centers, each 24×24 pixels. They measure baseline model-reproduction error, not fresh camera accuracy for the new candidates. Some extreme-condition maxima remain high; not every patch is below ΔE00=3.

| Look | Model/camera mean ΔE00 | P95 | RGB ROI-mean RMSE |
|---|---:|---:|---:|
| CC | 0.821 | 1.976 | 1.571 |
| PROVIA | 1.185 | 3.674 | 3.752 |
| VELVIA | 1.462 | 4.267 | 4.883 |
| ASTIA | 1.085 | 3.128 | 3.188 |
| REALA_ACE | 0.650 | 1.230 | 1.317 |
| PRO_NEG_HI | 0.983 | 2.822 | 2.129 |
| PRO_NEG_STD | 0.730 | 1.461 | 1.306 |
| CLASSIC_NEG | 0.905 | 1.569 | 2.449 |
| NOSTALGIC_NEG | 0.710 | 1.285 | 1.896 |
| ETERNA | 0.749 | 1.608 | 1.289 |
| ETERNA_BLEACH_BYPASS | 0.747 | 1.407 | 1.310 |
| ACROS | 1.121 | 2.431 | 1.583 |

## Acknowledgements

[751K/sony-look-bridge](https://github.com/751K/sony-look-bridge) provides the Sony Edit RAW operators and Creative Look arithmetic used by the local M4 model's native frontend. [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) provides native-parameter references and fitting research. Source photographs, reference TIFFs, weights, Sony executables and extracted constants are not included in this report.
