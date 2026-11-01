# AWB priority implementation

## Parameter identity

In the supported M4 layout, the menu/request enum is `0=STANDARD`, `1=AMBIENCE`, `2=WHITE`. AP places it at byte `+0x12` of the `0x4006` white-balance message. The CP snapshot stores the effective AWB priority at `C+0x23`; the original non-AWB gate remains intact.

The factory configuration lives in BK4 record `0x02A40000`, size `0x1200`. Its runtime base is `G=0x01229218`:

| Record-relative field | M4 factory value | FX2 factory comparison | Recipe effective value |
|---|---:|---:|---:|
| `+0x931`, signed byte | −24 (`E8`) | −1 (`FF`) | −1 |
| Standard branch | 0 from code | 0 from code | 0 |
| `+0x930`, signed byte | 88 (`58`) | 88 (`58`) | 97 (`61`) |

The FX2 comparison is from official 1.01 data. **White=97 is a custom choice, not an FX2 factory value or a complete FX2 AWB port.** The recipe does not copy FX2 addresses, runtime layout or other coefficients.

`+0x930/+0x931` above are record-relative fields, not DAT or CP file offsets. This recipe changes the CP consumers instead of rewriting the BK4 record, so previously retained backup values do not override these two inputs.

## Exact CP edits

The CP linked base is `0x00108000`. For the supported file, `file_offset = linked_VA − 0x00108000`.

| CP file offset | Linked VA | Original bytes and instruction | Replacement |
|---|---|---|---|
| `0x13293E` | `0x23A93E` | `96 F8 30 19`, `LDRB.W r1,[r6,#0x930]` | `4F F0 61 01`, `MOV.W r1,#97` |
| `0x132948` | `0x23A948` | `96 F8 31 19`, `LDRB.W r1,[r6,#0x931]` | `4F F0 FF 01`, `MOV.W r1,#255` |

Each replacement is one four-byte Thumb instruction. `MOV.W` without `S` preserves flags as the original load did. The following `SXTAB` interprets the low byte `FF` as −1. All other CP bytes and the component length remain identical.

The Standard branch at file `0x132952..0x132956` retains `00 21 00 23` (`MOVS r1,#0; MOVS r3,#0`). No branch redirection, new code region, heap allocation or thread is introduced.

## Local arithmetic and boundaries

In the checked M4 defaults, the relevant base fields `+0x903/+0x904/+0x911/+0x912` are all `128`. The bounded operation can be reconstructed as:

```c
/* Analyst reconstruction of the local operation, not original source. */
int p = priority == 2 ? 97 : priority == 1 ? -1 : 0;
int a = 2 * (128 + p);
```

This gives Ambience `254`, Standard `256`, White `450`. One later linear segment uses a denominator of `512`; the corresponding ratios are `49.609375%`, `50%`, and `87.890625%`. They are local coefficients, not global warmth-removal percentages or final colour temperatures.

Signed-byte encoding is significant: `0x7F` is +127 and gives `a=510`; `0x80` is −128 and gives `a=0`. Changing a requested value requires updating the recipe, recomputing complete output identities and repeating native/integration verification. Merely increasing an unsigned byte is not a valid tuning procedure.

Other fields, including `+0x932/+0x933`, mode gates and the remaining AWB fusion, still participate in the result. Their retention does not establish full equivalence between cameras.

## Input contracts and composition

[The profile](../../a7m4/profiles/awb-priority.json) lists the complete stock and integrated CP input/output pairs. The tool hashes the full input before editing, verifies each original span, and checks the complete expected result before creating a new output file.

Apply AWB after the current sound-handoff CP layer. The integrated input is the output of [custom-sound-handoff.json](../../a7m4/profiles/custom-sound-handoff.json); the AWB output is the next component in that chain. The existing LUT reference remains the input-side reference for this optional method. Preserve its AP, resource, Gamma, sound and aspect components rather than replacing them with older standalone versions.

For other CP variants, review the containing functions, instruction boundaries, signed arithmetic, backup/snapshot layout and modifications from every feature. Recompute full hashes and review boot/mapping behavior before adding support. The camera's displayed firmware label does not establish layout compatibility.

Final FAT replacement, partition-checksum updates, DAT encoding and update signing are separate integration steps. Verify the CP extracted from the final package against the recipe result; do not treat the component file as a whole partition or flashable package.
