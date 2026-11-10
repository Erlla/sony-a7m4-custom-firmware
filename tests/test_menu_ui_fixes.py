import json

import pytest
from a7m4 import menu_ui_fixes as ui
from a7m4.icon_lz4k import encode,decode


@pytest.mark.parametrize('component',sorted(ui.LAYOUT['components']))
def test_unknown_component_input_rejected_before_build(component):
    with pytest.raises(ValueError,match=component+' input: SHA-256 mismatch'):
        ui.compose(b'wrong component',component)


def test_native_sources_match_exact_recipe():
    for name,value in ui.LAYOUT['components']['lut-touch']['sources'].items():
        ui.check_hash((ui.NATIVE/name).read_bytes(),value,name)


def test_current_ap_chain_and_resource_binding():
    lut=json.loads((ui.ROOT/'methods/08-custom-lut/reference-layout.json').read_text('utf8'))
    stages=ui.LAYOUT['components']
    assert lut['aspect_playback']['components']['ap']['output_sha256']==stages['lut-touch']['input_sha256']
    assert stages['lut-touch']['output_sha256']==stages['aspect-ap']['input_sha256']
    assert next(x['sha256']for x in lut['components']if x['component']=='AP')==stages['aspect-ap']['output_sha256']
    assert lut['menu_ui_fixes']['resource_components']==['image-23','image-32']
    assert stages['image-23']['indices']==stages['image-32']['indices']==list(range(0x1e98,0x1e9c))


def test_compact_artwork_preserves_centered_source_pixels():
    # Rows are distinct, so an incorrect vertical crop or stride is visible.
    source=b''.join(bytes([y])*160 for y in range(60))
    menu=ui.compact(source)
    assert len(menu)==6400
    for y in (0,19,39):assert menu[y*160+6:y*160+146]==bytes([y+10])*140


def test_resource_codec_resets_dictionary_at_block_boundary():
    pixels=bytes(range(256))*25
    decoded,blocks=decode(encode(pixels))
    assert decoded==pixels and[b['output_bytes']for b in blocks]==[4096,2304]
    with pytest.raises(ValueError):decode(b'\xf0\x01\x00\x01')
