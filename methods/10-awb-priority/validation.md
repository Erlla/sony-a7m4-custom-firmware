# Validation scope

The recipe is supported by exact component identities and bounded execution evidence. It is not a claim of improved colour in every scene or physical camera acceptance.

| Evidence | What it establishes | Limit |
|---|---|---|
| M4 factory records | All 32 checked upgrade profiles have the same CC0 record; Ambience −24 and White +88 | Upgrade defaults, not the current camera's backup/readback |
| FX2 factory comparison | All 11 checked profiles have Ambience −1 and White +88 | Does not establish a full AWB algorithm port |
| Original M4/FX2 coefficient blocks | Signed-byte arithmetic and boundary behavior; both relevant context branches | Bounded blocks with synthetic state |
| Integrated CP candidate versus its input | Exactly eight changed bytes; Standard and all other CP bytes retained | Applies to the listed complete identities |
| Candidate native AWB replay | Three priority modes, two contexts and four backup-value combinations produce 254/256/450 | No complete AWB or image-quality execution |
| Original integrated BOOT/BODY/MMU replay | Register/flag/page-map results and existing optional-module readiness retained | Modeled RAM; no physical cache, DMA or boot observation |
| Local full-package audit | FAT replacement/readback, plaintext complement, partition CRCs, full decode comparison and user-key signature | No physical installation or current-receiver compatibility claim |

The published patcher is separately checked against both supported complete inputs. Its integrated output must equal the locally audited component `8f3061af864a86f49c03d62301af0dd193d493251b2058731149924d676cc939`. Neither complete manufacturer inputs nor derivative firmware binaries are distributed here.

Host-side fixture tests cover rejected unknown input, incorrect original bytes, overlapping edits, incorrect output identity and refusal to overwrite an existing output. Those tests exercise tool contracts; they do not stand in for native firmware execution.

After integrating a new complete package, independently extract and identify CP, check every partition checksum, decode the final container against the intended plaintext, and verify its accepted signing chain. Then validate normal boot, the three AWB priorities, capture and playback on the camera under fixed lighting. Results for manual white balance, other modes, other bodies and arbitrary combined layouts are outside the current evidence.
