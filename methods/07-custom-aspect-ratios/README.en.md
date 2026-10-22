# Custom aspect ratios: 17:6, 65:24, 5:4 and 7:6

[中文](README.md) · [Method index](../../README.en.md)

Adds **17:6, 65:24, 5:4 and 7:6** to the existing Aspect Ratio setting on the Sony A7 IV (ILCE-7M4), alongside the stock 3:2, 4:3, 16:9 and 1:1 options. Selection uses the existing menu or Fn menu, with matching labels, Fn icons and live-view masks. The maintainer confirmed landscape and portrait previews on the **6.63 T22** feature build.

This page documents the final functionality, implementation and camera examples. A complete firmware requires integration against compatible programs and resources; this page provides neither a standalone installer nor a complete firmware download. See the [main project requirements](../../README.en.md).

## Resulting behavior

| Item | Behavior |
| --- | --- |
| Added ratios | 17:6, 65:24, 5:4 and 7:6, alongside the four stock options |
| JPEG / HEIF | Center-cropped output using the selected ratio and the encoder's pixel-alignment requirements |
| RAW | Original image area retained; the JPEG in RAW+JPEG uses the selected crop |
| Labels and Fn icons | Display the selected custom ratio |
| Aspect-ratio selection page | Preview follows the highlighted option; confirmation applies it, cancellation returns to the saved selection |
| Fn menu and shooting view | Show the mask for the selected ratio |
| Orientation changes | Transform the mask using the screen direction and display mapping for landscape and portrait previews |

## Preview masks

**Custom-ratio live view uses masks to mark the crop area. Some parameter-setting pages may temporarily show the original 3:2 preview. Returning to the shooting view restores the selected ratio's mask. This affects only the preview on those settings pages: JPEG/HEIF output still uses the selected crop, while RAW retains its original image area.**

Preview masking and photo cropping are separate processing paths. Masks guide composition; JPEG/HEIF images are actually cropped to the target ratio, rather than saved with black borders.

## Operation

1. Open Aspect Ratio from the camera menu or the Fn menu.
2. Select 17:6, 65:24, 5:4 or 7:6 after the stock options, then confirm.
3. Compose within the visible mask in the shooting view. The mask follows display orientation when the camera rotates.
4. Save JPEG / HEIF for cropped output; also save RAW when the original image area is needed.

## Final implementation

| Component | Implementation |
| --- | --- |
| Menu and resources | Extend the original option list with four entries and matching text, list presentation and Fn icons |
| Selection state | Keep the highlighted and confirmed ratios distinct for browsing and capture, preserving confirm, cancel and saved-selection behavior |
| Image output | Pass the target ratio to the JPEG/HEIF center-crop paths, calculate dimensions with encoder alignment, and preserve RAW geometry |
| Preview drawing | Calculate two mask regions from the live-view rectangle, pixel aspect ratio and selected ratio for the shooting view, Fn menu and aspect-ratio selection page |
| Orientation | Calculate in physical live-view coordinates, then transform the entire rectangle using direction and display mapping from the same native snapshot during page creation, refresh and rotation |

For input dimensions `W × H` and target ratio `N:D`, a wider input retains height and crops the sides; a taller input retains width and crops the top and bottom. Final dimensions follow encoder alignment. Preview geometry also accounts for display pixel aspect ratio, and rotation transforms both rectangle position and dimensions.

The implementation combines AP changes, image-cropping paths and matching UI resources. Ports to another firmware require matching source hashes, address layouts and calling contracts; the displayed version alone does not identify a compatible binary.

## Camera examples

The maintainer supplied and authorized publication of these two **65:24** examples. Location and other metadata were removed from the public copies; compressed image data and decoded pixels are unchanged.

### Fn menu

![Fn menu showing the 65:24 icon and corresponding preview mask](assets/fn-65-24.jpg)

### Aspect-ratio selection page

![Aspect-ratio page showing the four added options with 65:24 selected and masked](assets/selection-65-24.jpg)

## Validation results

The maintainer confirmed correct labels, Fn icons and captured image dimensions, then confirmed that landscape and portrait previews both work in the 6.63 T22 test. JPEG crop dimensions and original RAW geometry have sample-based checks. The photos above show the 65:24 interface. HEIF is included in the crop implementation; this page does not supply a separate measured HEIF camera sample.

The selection-page implementation passed 336 native creation/rotation/mask-clearing cases, 3,475 drawing checks and 3,968 calling-convention checks. The final installation package passed signature, 739,727-block, partition-CRC and target-file verification. Hardware acceptance refers to the maintainer's single A7M4 and does not certify arbitrary models, firmware combinations or every output device.

Photo identities are in [assets/manifest.json](assets/manifest.json); see [third-party notices](../../THIRD_PARTY_NOTICES.md) for authorization details.
