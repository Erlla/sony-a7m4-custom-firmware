# Custom sound test samples

[中文](README.md) · [Custom sound feature and integration](../../methods/06-custom-sounds/README.en.md)

`YEAH.WAV`, `DAGOU.WAV` and `JIAO.WAV` are user-supplied samples explicitly authorized for public reference and testing. They retain their original bytes, without re-encoding, normalization or gain changes. See the [sample notice](../../THIRD_PARTY_NOTICES.md#reference-sound-samples--参考音频); the MIT license for the project's original code does not automatically apply to these audio files.

## Import into the camera

The custom sound feature must already be integrated. Copying WAVs alone does not install it. See the [method guide](../../methods/06-custom-sounds/README.en.md) for complete firmware integration requirements.

1. Download the original WAV files you want to try and copy them to `PRIVATE/SONY/PRO/SOUNDS/` on the SD card.
2. Under Shooting → Shutter/Silent, enter Custom electronic shutter sound or Custom focus sound and turn its switch on.
3. Choose Import from SD, select one file and confirm. The saved filename appears in the menu after successful import. Each sound slot selects one WAV; the two slots may use the same or different files.

Test focus with an AF-S half-press, then switch to MF and take an electronic single shot to test shutter sound separately. Keep silent mode off and enable the stock focus signal for the focus test. 50% volume is the feature's reference gain; 100% doubles that digital amplitude. Different recordings may have different perceived loudness.

## File parameters and checksums

All three files are integer PCM (format 1), 44,100 Hz, 16-bit stereo, within the parser's 1 MiB / 5-second limit. Durations below are calculated from PCM frame counts; the camera picker has no duration column. This publication checked file format and integrity without adding any new hardware test claim.

| File | Bytes | PCM frames | Duration |
|---|---:|---:|---:|
| [YEAH.WAV](YEAH.WAV) | 196686 | 49152 | 1.115 s |
| [DAGOU.WAV](DAGOU.WAV) | 86094 | 21504 | 0.488 s |
| [JIAO.WAV](JIAO.WAV) | 86094 | 21504 | 0.488 s |

Exact parameters and SHA-256 checksums are recorded in [manifest.json](manifest.json). From the repository root, run:

```powershell
Get-FileHash .\examples\custom-sounds\*.WAV -Algorithm SHA256
```

| File | SHA-256 |
|---|---|
| YEAH.WAV | `01a907cdc8576dbc7b955ddc90b8e116e52ca634c5ad5d4482c3a79dc030cf5f` |
| DAGOU.WAV | `8ab0b01ef8361e5fc3c53e800dbd4572eec437aa3c163ab58e1b45d707b023ca` |
| JIAO.WAV | `c48b70b49e64cb64a4ceb19efb5f912d542c2255f369ca99f48882716a465ebe` |
