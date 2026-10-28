# Custom shutter and focus sounds

[中文](README.md) · [Implementation map](IMPLEMENTATION.md) · [Native source and build](../../native/custom-sounds/README.md)

Adds **Custom Shutter Sound** and **Custom Focus Sound** under Shooting → Shutter/Silent. **Mechanical, electronic front-curtain and electronic shutter modes can all play the imported shutter sound.** They share the shutter slot’s switch, WAV and volume. Switching shutter types preserves the setting. The mechanical shutter’s physical sound remains audible; the custom sound plays through the speaker.

AF-S / AF-A focus confirmation uses a separate clip or the stock default. Each sound slot stores its own switch, WAV and volume. Silent mode suppresses both custom sounds.

Focus and shutter sounds **preempt each other, with the latest trigger taking priority**. Focus confirmation interrupts a playing shutter clip; taking a photo interrupts the focus clip. During a burst, each new exposure retriggers the sound. After activity stops, the final clip finishes naturally without replaying older requests.

## Files and operation

Place WAV files in **`PRIVATE/M4ROOT/GENERAL/SOUNDS/`** from the SD card root:

```text
PRIVATE/
└─ M4ROOT/
   └─ GENERAL/
      └─ SOUNDS/
         ├─ shutter.wav
         └─ focus.wav
```

1. Open Shooting → Shutter/Silent → Custom Shutter Sound and enable it.
2. Select Import from SD, choose the card and a WAV, then confirm.
3. Set the volume. Mechanical, electronic front-curtain and electronic shutters share this clip.
4. To customize focus confirmation, select a separate WAV under Custom Focus Sound, using the same directory.

Imported audio and filenames are saved internally and restored after power-on. The original card need not remain inserted. Existing saved clips remain usable; files for a new import belong in the directory above.

| Item | Behaviour |
|---|---|
| Shutter sound | Available with mechanical, electronic front-curtain and electronic shutters; changing shutter type preserves its switch |
| Focus sound | Separate AF-S / AF-A clip or Default; AF-C and MF retain their existing rules |
| Volume | Independent 10%–100% levels in 10% steps; 50% is reference gain, 100% doubles the reference digital amplitude |
| Switch off | Disables that slot’s import and volume rows without disabling the other slot |
| Silent mode | Suppresses both custom sounds; existing selections resume when silence is disabled |
| File picker | WAV filenames, orange selection highlight and audio-specific confirmation |

Use short integer PCM WAV files: format 1, mono/stereo, 8/16/24/32 bits, 8–192 kHz, at most 1 MiB and 5 seconds. Compressed/floating-point WAV, damaged RIFF/chunks and unsafe filenames are rejected. User-authorized [YEAH.WAV, DAGOU.WAV and JIAO.WAV examples](../../examples/custom-sounds/README.en.md) are available.

The stock focus-signal setting also controls custom focus playback. Focus sound requires an actual focus-confirmation event. When focus and capture events arrive in succession, the latest trigger takes priority.

## Camera demo photos

**Menu location: custom shutter sound with mechanical shutter and electronic front-curtain enabled**

| Custom shutter sound | Custom focus sound |
|---|---|
| ![Mechanical shutter and electronic front-curtain enabled with the Custom Shutter Sound menu](images/shutter-menu-location.png) | ![Custom Focus Sound menu location](images/focus-sound-menu-location.jpg) |

**Independent switches, clips and volume**

| Shutter sound: Ciallo.wav, 100% | Focus sound: YEAH.WAV, 100% |
|---|---|
| ![Custom Shutter Sound enabled with Ciallo.wav and volume at 100%](images/shutter-settings.png) | ![Custom Focus Sound enabled with YEAH.WAV and volume at 100%](images/focus-sound-settings.jpg) |

**Select Import from SD to browse WAV files**

![Audio file picker](images/audio-import-picker.jpg)

## Reconstruct modified components

The repository distributes authored source and change recipes, without complete Sony firmware. The reference AP already contains the shared menu framework; **stock AP is not interchangeable**. Complete per-file SHA-256 hashes and the address layout establish compatibility.

```powershell
python -m a7m4.custom_sound inspect
python -m a7m4.custom_sound apply --ap local/sound-input/appFw.so --cp local/sound-input/cpapp-b.bin --fs-root local/sound-input/fs --output output/custom-sounds
```

Supply the exact AP, CP, `fs/lib/libmpr.so` and all 68 horizontal/vertical language resources listed by `inspect`. Outputs contain AP, MPR, resources, CP and a verification manifest, including mechanical shutter support, the current menu name and sound directory. Input files and existing outputs are preserved.

That command reconstructs its pinned basic sound layout. Apply mutual preemption separately to the complete CP in the current LUT/aspect integration layout:

```powershell
python -m a7m4.custom_sound_handoff --input local/integrated/cpapp-b.bin --output output/cpapp-b.handoff.bin
```

The [handoff recipe](../../a7m4/profiles/custom-sound-handoff.json) lists exact input/output hashes. The basic sound recipe's CP is not interchangeable with this integrated input. See the [handoff module](../../native/custom-sounds/handoff/README.md) for source and reproducible section builds.

For missing or incorrect menu text, see the [resource-only repair](menu-resource-repair.md). After full-package integration, extract the final filesystem and run:

```powershell
python -m a7m4.custom_sound verify-resources --fs-root local/final-package-fs
```

## Source and firmware integration

The [implementation map](IMPLEMENTATION.md) identifies shutter policy, directory construction, menu resource IDs, persistence, AP/CP ownership and volume changes. The [native build guide](../../native/custom-sounds/README.md) covers all six modules, address-preserving post-link edits and generation of current-policy sources.

A complete firmware build integrates AP, MPR, all language resources and CP together, recalculates container/partition checksums and signatures, and synchronizes the independent CP NOR through the supported SD update path. The component `cpapp-b.bin` is not a whole partition image. Different layouts require renewed address, calling-contract, memory-ownership and runtime checks.

SD JSON/multi-slot LUTs share AP registration, GUI lifecycle, language banks and CP boot/dispatch with sound. Follow the [LUT integration rules](../08-custom-lut/INTEGRATION.md); preserve already-composed features when modifying components.
