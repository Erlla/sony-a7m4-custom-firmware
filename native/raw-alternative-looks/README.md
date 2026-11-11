# Camera-written RAW alternative looks

This authored Thumb component extends the existing SR2 alternative-look list from ten to twelve entries. It prepares three bytes of the current model's RAM configuration before the original constructor, retains the native field/gamma/WB producers and fixes the two added RAW gamma colour mappings.

The exact recipe accepts the documented integrated CP after capture-copy inheritance and optional AWB. It does not reconstruct the earlier FL2/FL3 port from stock inputs. See the [Chinese method](../../methods/03-fl2-fl3/raw-alternative-looks.md) or [English method](../../methods/03-fl2-fl3/raw-alternative-looks.en.md) for addresses, component order and the offline command.

`raw_list.c` and `raw_list.ld` rebuild three sections: a resident constructor wrapper and native quantity/mapping implementations. `layout.json` pins the compiler, sources, complete CP identities, section identities and patch preimages. The wrapper uses existing resident space; the optional P3 prefix and its CRC remain unchanged.

The maintainer reported that Edit recognizes FL2/FL3 from the resulting camera RAW. See [validation scope](../../methods/03-fl2-fl3/raw-alternative-looks-validation.md). No firmware, manufacturer program, calibration record or camera photo is included here.
