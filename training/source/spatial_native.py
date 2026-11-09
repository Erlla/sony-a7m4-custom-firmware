import support as w
import numpy as np
import native_frontend as E

def native_pixels(row,native,atlas,model):
    import sony_render as R
    import sony_detail as SD
    import sony_sscs as SC
    import decoder_params as DP
    import sr2
    raw=row['raw']['path']
    with E.selected_record(raw,native,'endpoint0-legacy','fixed'):
        look=R.Look('Standard',R.load_looks(raw),fade=0,use_rust=False)
        iso=int(DP.decoder_params(raw)['iso'])
        detail=dict(sharp=SD.sharpness_params(),spica=(SD.load_srsettings(),SD.spica_params(iso)),dev208=0,dev2c4=50)
        tags={k:(v[1]if isinstance(v[1],list)else[v[1]])for k,v in sr2.sr2_subifd(raw).items()}
        a=np.load(atlas['linear']['path'],mmap_mode='r')
        output=look.render(a,detail=detail,sscs=SC.params_from_tags(tags),strip=128)
    selection=np.load(atlas['selection']['path'])
    return (output[selection['y'],selection['x']]<<2),selection['ends']
