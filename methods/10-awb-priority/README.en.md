# White-balance tuning: AWB priority configuration

[中文](README.md) · [Implementation and patch locations](IMPLEMENTATION.md) · [Inputs and layout](reference-layout.json) · [Validation scope](validation.md)

Set **Ambience priority to −1, retain Standard at 0, and set White priority to 97**. The existing three camera settings remain available; this method adds no menu and does not change manual colour temperature.

## Sony FX2 factory parameters and recipe comparison

**Sony FX2 official firmware 1.01 factory parameters:**

| Setting | FX2 factory parameter | Corresponding local coefficient |
|---|---:|---:|
| Ambience priority | −1 | 254 |
| Standard | 0 | 256 |
| White priority | 88 | 432 |

The Ambience and White parameters come from 11 checked upgrade profiles in official FX2 firmware 1.01; the Standard branch uses 0 in code. See [parameter identity](IMPLEMENTATION.md#parameter-identity) and [validation scope](validation.md) for the fields and source.

**This recipe's parameters:**

| Setting | Recipe parameter | Corresponding local coefficient |
|---|---:|---:|
| Ambience priority | −1 | 254 |
| Standard | 0 | 256 |
| White priority | 97 | 450 |

The recipe's Ambience and Standard parameters match the FX2 factory values above. **White priority 97 is a custom choice; the FX2 factory value is 88.** The listed coefficients belong to a local AWB operation, not final colour temperatures or overall warmth-removal percentages. Final colour depends on the light source, scene and other tuning. This method does not promise improved white balance in every scene.

## Produce the modified CP component

The supported layout derives from official Sony ILCE-7M4 firmware 6.02. The tool accepts the listed complete stock and integrated CP identities, including the sound lifecycle and Capture-copy aspect layers. See the full hashes in the [patch profile](../../a7m4/profiles/awb-priority.json); the displayed camera version is insufficient to identify a compatible input.

Run from the repository root:

```powershell
python -m a7m4.awb_priority --input local/cpapp-b.bin --output output/cpapp-b.awb.bin
```

Obtain the supported input separately. Create the output parent directory first. The command preserves the input, refuses an existing output, and prints the output SHA-256. An unsupported complete hash or mismatched original instruction is rejected.

## Combine with existing features

For the [integrated layout](../08-custom-lut/INTEGRATION.md), complete the existing features and [mutual sound handoff](../06-custom-sounds/README.en.md) first, then add [Capture-copy aspect inheritance](../../native/aspect-capture-clone/README.md) and apply AWB to that CP output:

```powershell
python -m a7m4.custom_sound_handoff --input local/integrated/cpapp-b.bin --output output/cpapp-b.handoff.bin
python -m a7m4.custom_sound_lifecycle --component cp --input output/cpapp-b.handoff.bin --output output/cpapp-b.sound-lifecycle.bin
python -m a7m4.aspect_capture_clone --input output/cpapp-b.sound-lifecycle.bin --compiler path/to/arm-none-eabi-gcc.exe --output output/cpapp-b.aspect-copy.bin
python -m a7m4.awb_priority --input output/cpapp-b.aspect-copy.bin --output output/cpapp-b.awb.bin
```

These are alternative routes for the listed supported inputs. A stock CP cannot replace a combined CP that already contains LUT, aspect-ratio and sound features. Any other combination needs a new complete identity and integration review.

## Firmware integration and use

The output is a CP file, not a complete partition or installable firmware package. Replace the matching file in its FAT image, update partition checksums, follow the [integration rules](../08-custom-lut/INTEGRATION.md) and [signing method](../01-custom-signing/README.en.md), then check the final package's CP hash, every partition CRC, decoded contents and signature. Use the established [installation procedure](../../no-fastboot-install/README.en.md).

After installation, select Auto White Balance and switch between the existing Standard, Ambience and White priority modes. Compare the same scene under fixed lighting and check capture and playback separately.

The method fixes two inputs at their actual read sites while retaining the Standard branch. It does not write camera backup records. An upgrade-default record can still show its original values while these read sites use the recipe. See [implementation](IMPLEMENTATION.md) for the eight-byte change and signed-byte boundary, and [validation](validation.md) for the limits of installation and image-quality evidence.
