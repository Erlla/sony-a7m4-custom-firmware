from pathlib import Path
from contextlib import contextmanager
import base64, struct, time
import numpy as np
import support as w
import support as lab
import edit_bridge
import effective_native
def configure(model):
    return model["identity"]
def sr2_entries(raw):
    import sr2
    return [dict(tag=k, type=v[0], count=len(v[2])//2, data=v[2]) for k,v in sr2.sr2_subifd(str(raw)).items() if k in (0x7841,0x7842,0x7843,0x7844,0x7845,0x7846,0x7847,0x7848,0x7801)]

def selected_tags(raw, native=None, mapping='endpoint0-legacy', wb_mode='fixed'):
    import arw_looks as AL
    tags = dict(AL.main_tags(str(raw)))
    receipt = dict(matrix_mapping='selected-ARW', gamma_mapping='selected-ARW')
    if native is None:
        return tags, receipt
    payload = edit_bridge.photo_payloads(native)
    if mapping == 'effective-fixed':
        fields = effective_native.cc1.decode_sr2_fields(sr2_entries(raw))
        context = effective_native.fixed_context(fields, wb_mode)
        matrices = effective_native.matrix_payloads(native, context)
        payload.update({key: matrices[key] for key in ('matrix96', 'matrix9')})
        receipt['matrix_mapping'] = matrices['mapping']
    elif mapping == 'endpoint0-legacy':
        receipt['matrix_mapping'] = 'photo endpoint0, all 16 sectors; historical mapping'
    else:
        raise ValueError('Unknown native mapping')
    old = base64.b64decode(str(tags['0x780f']).removeprefix('base64:'))
    tags['0x780f'] = 'base64:' + base64.b64encode(old[:24] + payload['matrix96'] + old[216:]).decode()
    for key, binary, fmt in (('0x7800', payload['matrix9'], '<9h'),
                             ('0x7805', payload['gamma_axis'], '<128i'),
                             ('0x7806', payload['gamma'], '<128i')):
        tags[key] = ' '.join(map(str, struct.unpack(fmt, binary)))
    for tag, binary in payload['cc'].items():
        tags[f'0x{tag:04x}'] = ' '.join(map(str, struct.unpack('<8h', binary)))
    receipt.update(gamma_mapping='photo context6, explicit knot axis and values',
                   coefficients='B/A1/A2 plus captured SR2 7848 weights, int16/Q10 selection',
                   actual_weights=tags['0x7848'], source_RAW_untouched=True)
    return tags, receipt


@contextmanager
def selected_record(raw, native, mapping, wb_mode):
    """Temporary upstream call adapter; restored even when decoding fails."""
    import sony_render as R
    import develop_settings as DS
    import arw_looks as AL
    tags, receipt = selected_tags(raw, native, mapping, wb_mode)
    old_load, old_settings = R.load_looks, DS.effective_settings
    def load(path):
        result = old_load(path)
        result['Standard'] = tags
        result['_main'].update({key: tags[key] for key in R.MAIN_TAGS})
        return result
    def settings(path):
        result = dict(old_settings(path))
        # WB remains the RAW's captured gains, including when capture was fixed.
        # Edit-saved WB/exposure edits do not silently alter the camera sample.
        result.update({DS.WB_MODE: 1, DS.EXPOSURE: 0, DS.FADE: 0})
        return result
    R.load_looks, DS.effective_settings = load, settings
    try:
        yield receipt
    finally:
        R.load_looks, DS.effective_settings = old_load, old_settings


def decode(raw, native, output, model, mapping='endpoint0-legacy', wb_mode='fixed', roi=None):
    identity = configure(model)
    import sony_decode as decoder
    import decoder_params as DP
    original_crop = DP.crop_rect
    if roi is not None:
        x, y, width, height = map(int, roi)
        if (x | y | width | height) & 1:
            raise ValueError('CFA ROI must be even-aligned')
        DP.crop_rect = lambda path: (x, y, x + width, y + height)
    started = time.monotonic()
    try:
        with selected_record(raw, native, mapping, wb_mode) as adapter:
            image = decoder.decode(str(raw), 'Standard', lens=False, nr=False, dro=False,
                                   marble=False, detail=True, rust=False, strip=128, verbose=True)
    finally:
        DP.crop_rect = original_crop
    from PIL import ImageCms
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    lab.tifffile.imwrite(output, image << 2, photometric='rgb', metadata=None,
                        extratags=[(34675, 'B', len(icc), icc, False)])
    return dict(schema='m4-explicit-native-render/1', identity=identity, adapter=adapter,
                seconds=time.monotonic()-started, shape=list(image.shape),
                pixel_domain='Sony RGB14 shifted left2 into RGB16', lens_correction=False,
                noise_reduction=False, DRO=False, marble=False, ITP=True, SSCS=True,
                sharpness_spica=True, roi=roi, uses_Sony_process=False)
