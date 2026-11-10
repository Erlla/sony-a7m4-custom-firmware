"""Build exact-layout LUT touch and aspect-menu icon components, offline."""
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile
from .icon_lz4k import encode, decode

if not __debug__:
    raise RuntimeError('Run without Python -O: binary invariant checks are required')

ROOT=Path(__file__).resolve().parents[1]
NATIVE=ROOT/'native/menu-ui-fixes'
LAYOUT=json.loads((NATIVE/'layout.json').read_text('utf8'))


def check_hash(data,expected,label):
    actual=hashlib.sha256(data).hexdigest()
    if actual!=expected:raise ValueError(f'{label}: SHA-256 mismatch: {actual} != {expected}')


def branch(pc,target):
    delta=target-pc
    assert delta%4==0 and -(1<<27)<=delta<(1<<27)
    return struct.pack('<I',0x14000000|((delta//4)&0x3ffffff))


def touch(data,profile,zig):
    if zig is None:raise ValueError('--zig is required for lut-touch')
    check_hash(Path(zig).read_bytes(),LAYOUT['compiler_sha256'],'Zig compiler')
    for name,value in profile['sources'].items():check_hash((NATIVE/name).read_bytes(),value,name)
    elf=ELFFile(BytesIO(data))
    i,rx=next((i,s)for i,s in enumerate(elf.iter_segments())if s['p_type']=='PT_LOAD'and s['p_vaddr']==int(profile['rx_VA'],0))
    assert rx['p_flags']==5 and rx['p_filesz']==rx['p_memsz']==profile['input_rx_bytes']
    helper=int(profile['helper_VA'],0);hook=int(profile['hook_VA'],0)
    at=rx['p_offset']+helper-rx['p_vaddr'];slot=rx['p_offset']+hook-rx['p_vaddr']
    assert data[slot:slot+4]==branch(hook,int(profile['original_dispatch_VA'],0))
    with tempfile.TemporaryDirectory(prefix='a7m4-menu-ui-')as tmp:
        module=Path(tmp)/'selector.elf'
        subprocess.run([str(zig),'cc','-target','aarch64-freestanding-none',
            '-mcpu=generic-neon-fp_armv8','-mgeneral-regs-only','-mno-outline-atomics',
            '-mstrict-align','-mbranch-protection=none','-fpie','-Os','-g','-std=c11',
            '-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-fno-stack-protector',
            '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-nostdlib','-static',
            '-Wl,-no-pie','-fvisibility=hidden','-Wl,-e,lut_selector_touch_dispatch',
            '-Wl,-T,'+str(NATIVE/'selector.ld'),str(NATIVE/'selector.c'),'-o',str(module)],check=True)
        linked=ELFFile(BytesIO(module.read_bytes()));text=linked.get_section_by_name('.text')
        assert text['sh_addr']==helper and text['sh_size']==profile['code_bytes']
        assert not[s for s in linked.iter_sections()if s['sh_type']in('SHT_REL','SHT_RELA','SHT_NOBITS')and s['sh_size']]
        assert not[s.name for s in linked.get_section_by_name('.symtab').iter_symbols()if s.name and s['st_shndx']=='SHN_UNDEF']
        code=text.data()
    check_hash(code,profile['code_sha256'],'compiled selector helper')
    assert not any(data[at:at+len(code)])
    output=bytearray(data);output[at:at+len(code)]=code;output[slot:slot+4]=branch(hook,helper)
    ph=elf['e_phoff']+i*elf['e_phentsize']+32
    output[ph:ph+16]=struct.pack('<QQ',profile['output_rx_bytes'],profile['output_rx_bytes'])
    return bytes(output)


def aspect_ap(data,profile):
    elf=ELFFile(BytesIO(data));base=int(profile['table_VA'],0)
    s=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=base<s['p_vaddr']+s['p_filesz'])
    output=bytearray(data)
    for j,resource in enumerate(profile['menu_resources']):
        pos=s['p_offset']+base-s['p_vaddr']+(profile['first_custom_row']+j)*profile['row_bytes']+profile['field_offset']
        assert struct.unpack_from('<I',data,pos)[0]==int(profile['old_resource'],0)
        struct.pack_into('<I',output,pos,int(resource,0))
    return bytes(output)


def records(data):
    assert data[:4]==b'uxd\7'and struct.unpack_from('<H',data,10)[0]==0
    packed=struct.unpack_from('<I',data,12)[0];count=packed&8191
    assert packed>>13==(count+1)//2
    base=(16+2*count+3)&~3;rows=[]
    for index in range(count):
        word=struct.unpack_from('<H',data,16+2*index)[0]
        if word==65535:continue
        at=base+4*word;key,flags=struct.unpack_from('<II',data,at)
        assert key==0x1a000000+index and flags in(0xc0000000,0xc8000000,0x40000000,0x48000000)
        relpos=36 if flags&0x08000000 else 16
        width,height=struct.unpack_from('<HH',data,at+8);n,rel=struct.unpack_from('<II',data,at+relpos-4)
        assert at+4+rel+n<=len(data)
        rows.append(dict(index=index,offset=at,flags=flags,width=width,height=height,bytes=n,
                         payload=at+4+rel,relative=rel,relative_field=relpos,descriptor_bytes=relpos+4))
    return count,base,rows


def compact(raw):
    assert len(raw)==80*60*2
    result=bytearray(struct.pack('<H',0xddd0)*(80*40))
    for y in range(40):result[(y*80+3)*2:(y*80+73)*2]=raw[((y+10)*80)*2:((y+10)*80+70)*2]
    return bytes(result)


def image_bank(data,profile):
    count,base,old=records(data);by={r['index']:r for r in old}
    assert all(i<count and data[16+2*i:18+2*i]==b'\xff\xff'for i in profile['indices'])
    insertion=min(r['payload']for r in old);extra=20*len(profile['indices'])
    assert insertion==max(r['offset']+r['descriptor_bytes']for r in old)
    output=bytearray(data[:insertion]+bytes(extra)+data[insertion:])
    for r in old:struct.pack_into('<I',output,r['offset']+r['relative_field'],r['relative']+extra)
    cursor=(max(r['payload']+r['bytes']for r in old)+extra+3)&~3
    assert not any(output[cursor:])
    for j,index in enumerate(profile['indices']):
        r=by[0x1e90+j];assert(r['width'],r['height'],r['flags'])==(70,60,0xc0000000)
        original,_=decode(data[r['payload']:r['payload']+r['bytes']])
        check_hash(original,profile['source_pixels_sha256'][j],'source artwork')
        pixels=compact(original);check_hash(pixels,profile['pixels_sha256'][j],'menu artwork')
        stream=encode(pixels);decoded,blocks=decode(stream)
        assert decoded==pixels and[b['output_bytes']for b in blocks]==[4096,2304]
        cursor=(cursor+3)&~3
        assert cursor+len(stream)<=len(data)and not any(output[cursor:cursor+len(stream)])
        at=insertion+20*j;word=(at-base)//4
        assert word<65535 and base+4*word==at
        struct.pack_into('<H',output,16+2*index,word)
        struct.pack_into('<IIHHII',output,at,0x1a000000+index,0xc0000000,76,40,len(stream),cursor-at-4)
        output[cursor:cursor+len(stream)]=stream;cursor+=len(stream)
    assert not any(output[len(data):]);del output[len(data):]
    newer={r['index']:r for r in records(output)[2]}
    for r in old:
        n=newer[r['index']]
        assert tuple(n[k]for k in('flags','width','height','bytes'))==tuple(r[k]for k in('flags','width','height','bytes'))
        assert output[n['payload']:n['payload']+n['bytes']]==data[r['payload']:r['payload']+r['bytes']]
    return bytes(output)


def compose(data,component,zig=None):
    profile=LAYOUT['components'][component]
    check_hash(data,profile['input_sha256'],component+' input')
    assert len(data)==profile['file_bytes']
    if component=='lut-touch':result=touch(data,profile,zig)
    elif component=='aspect-ap':result=aspect_ap(data,profile)
    else:result=image_bank(data,profile)
    assert len(result)==len(data)
    check_hash(result,profile['output_sha256'],component+' output')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component',choices=sorted(LAYOUT['components']),required=True)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--zig',type=Path)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Output exists; no file will be overwritten')
    result=compose(args.input.read_bytes(),args.component,args.zig)
    with args.output.open('xb')as stream:stream.write(result)
    print(json.dumps(dict(component=args.component,bytes=len(result),sha256=hashlib.sha256(result).hexdigest())))


if __name__=='__main__':main()
