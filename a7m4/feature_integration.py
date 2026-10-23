"""Exact-layout LUT/aspect/sound AP/CP/resource composition. Offline component output only.

Requires privately held exact input images listed in native/feature-integration/layout.json.
Never opens USB, signs a package or changes a device. Not a generic firmware patcher.
"""
from pathlib import Path
from io import BytesIO
import hashlib
import json
import struct
import subprocess
import tempfile
import zlib
import numpy as np
from elftools.elf.elffile import ELFFile

# This frozen recipe uses assertions for internal binary invariants. Refuse -O
# even for library callers; hash checks and output guards always remain active.
if not __debug__:
    raise RuntimeError("Run without Python -O: binary invariant checks are required")

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = json.loads((ROOT/'native/feature-integration/layout.json').read_text('utf8'))
BASE = 0x108000


def check_hash(data, expected, label):
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(f"{label}: SHA-256 mismatch: {actual} != {expected}")


def write_new(path, data):
    # Exclusive create, including a final race check after compilation.
    with Path(path).open('xb') as stream:
        stream.write(data)


def elf(b):
    return ELFFile(BytesIO(b))

def off(b, va):
    for s in elf(b).iter_segments():
        if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] <= va < s['p_vaddr'] + s['p_filesz']:
            return s['p_offset'] + va - s['p_vaddr']
    raise ValueError(hex(va))

def bl_target(b, va):
    ins, = struct.unpack_from('<I', b, off(b, va))
    assert ins & 0xfc000000 == 0x94000000
    imm = ins & 0x3ffffff
    return va + ((imm ^ 0x2000000) - 0x2000000) * 4

def a64_branch(pc, target, link=False):
    delta = target - pc
    assert delta % 4 == 0 and -(1 << 27) <= delta < (1 << 27)
    return struct.pack('<I', (0x94000000 if link else 0x14000000) | ((delta // 4) & 0x3ffffff))

def thumb_branch(pc, target, link=False):
    off = (target & ~1) - pc - 4
    assert off % 2 == 0 and -(1 << 24) <= off < (1 << 24)
    value = off & ((1 << 25) - 1)
    s, i1, i2 = value >> 24, (value >> 23) & 1, (value >> 22) & 1
    return struct.pack('<HH', 0xf000 | (s << 10) | ((value >> 12) & 1023),
                       (0xd000 if link else 0x9000) | ((i1 ^ s ^ 1) << 13) |
                       ((i2 ^ s ^ 1) << 11) | ((value >> 1) & 2047))

IDENTITY_EDITS = [('9a8bfb63b53dc5fcfe77bc06e773675459de556cc10a03ae2221a0e24ea0ea89', '92a1b6ccdd2a92e94af7377858c79b08595cbb86ccb4b9a0464015ea8bdabae3'), ('7805a2f0ba478eba00e3796a600d09897af8146027fd76e3edf7c1d645ade7b4', '50da0a94ccfc30234fb661c31e1ee76532eebc452ae1ac09844d5259a440fbc8')]


def compose_ap(b, m, a):
    for label, data in (("base", b), ("input", m), ("aspect", a)):
        check_hash(data, LAYOUT["input_AP"][label], label)
    e0, em, ea = elf(b), elf(m), elf(a)
    r0, rm, ra = [e.get_section_by_name('.rela.dyn') for e in (e0, em, ea)]
    rstart = rm['sh_offset']; rend = rstart + rm['sh_size']; oldend = rstart + r0['sh_size']
    assert ra['sh_size'] - r0['sh_size'] == 96
    assert rstart == r0['sh_offset'] == ra['sh_offset']
    # Metadata fields are reconciled as complete values, never byte-wise.
    skip = np.zeros(len(b), dtype=bool)
    skip[:64] = True; skip[oldend:oldend+96] = True
    skip[0x59cf418:0x59cf420] = True; skip[0x5da95f8:0x5da9600] = True
    skip[0x1732000:0x1732004] = True; skip[0x173210c:0x1732110] = True
    x, y, z = [np.frombuffer(v[:len(b)], dtype=np.uint8) for v in (b, m, a)]
    delta = (x != z) & ~skip
    assert not np.any(delta & (x != y) & (y != z)), 'unaccounted semantic collision'
    merged = bytearray(m + bytes(len(a) - len(m)))
    dst = np.frombuffer(merged, dtype=np.uint8)
    dst[:len(b)][delta] = z[delta]
    del dst
    newloads = [s for s in ea.iter_segments() if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] >= 0x9010000]
    assert [s['p_vaddr'] for s in newloads] == [0x9010000, 0x9020000]
    for s in newloads:
        p, n = s['p_offset'], s['p_filesz']
        assert p >= len(m)
        merged[p:p+n] = a[p:p+n]
    # AB60..AB63 are current sound-dialog resources. Relocate ONLY aspect
    # references in its own two new segments; never globally replace IDs.
    text_id_edits=[]
    for i in range(4):
        old,new=0x200ab60+i,0x200ab4c+i
        assert m.count(struct.pack('<I',new))==0
        for s in newloads:
            lo,hi=s['p_offset'],s['p_offset']+s['p_filesz'];cursor=lo
            while (p:=merged.find(struct.pack('<I',old),cursor,hi))>=0:
                merged[p:p+4]=struct.pack('<I',new);cursor=p+4
                text_id_edits.append(dict(offset=p,old=hex(old),new=hex(new)))
        assert sum(e['old']==hex(old) for e in text_id_edits)==2
    phoff = newloads[0]['p_offset']; phva = newloads[0]['p_vaddr']
    oldphoff, phnum, phsz = em['e_phoff'], em['e_phnum'], em['e_phentsize']
    assert phsz == 56 and phnum == 11
    ph = [bytearray(m[oldphoff+i*56:oldphoff+(i+1)*56]) for i in range(phnum)]
    for entry in ph:
        if struct.unpack_from('<I', entry)[0] == 6:
            struct.pack_into('<QQQQQ', entry, 8, phoff, phva, phva, (phnum+2)*56, (phnum+2)*56)
    for i, s in enumerate(ea.iter_segments()):
        if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] >= 0x9010000:
            ph.append(bytearray(a[ea['e_phoff']+i*56:ea['e_phoff']+(i+1)*56]))
    assert len(ph) == 13 and len(ph)*56 < 0x400
    merged[phoff:phoff+len(ph)*56] = b''.join(ph)
    struct.pack_into('<Q', merged, 32, phoff); struct.pack_into('<H', merged, 56, len(ph))
    # Append four registry relocations AFTER all 106 main additions.
    # The old PLT relocation area is reserved capacity: live .rela.plt was
    # relocated to 0x8f64be8 by main. Prove both loader and section agree.
    liveplt = em.get_section_by_name('.rela.plt')
    tags = {t['d_tag']: t['d_val'] for t in em.get_section_by_name('.dynamic').iter_tags()}
    assert tags['DT_JMPREL'] == liveplt['sh_addr'] > rend+96
    assert rend+96 < em.get_section_by_name('.init')['sh_offset']
    assert not any(s['sh_type'] != 'SHT_NOBITS' and s['sh_size'] and
                   s['sh_offset'] < rend+96 and rend < s['sh_offset']+s['sh_size']
                   for s in em.iter_sections() if s.name != '.rela.dyn')
    newrela = a[oldend:oldend+96]
    assert [struct.unpack_from('<QQQ', newrela, i) for i in range(0,96,24)] == [
        (0x9020400+i*16+8,1027,0x9020000+(i+4)*128) for i in range(4)]
    merged[rend:rend+96] = newrela
    struct.pack_into('<Q', merged, 0x59cf418, rm['sh_size']+96)
    struct.pack_into('<Q', merged, 0x5da95f8, rm['sh_size']+96)
    chains = []
    for site, fn, original in ((0x1732000,0x90108b8,0x50bbdd0),(0x173210c,0x90108e0,0x1cd1934)):
        assert bl_target(a, site) == fn and bl_target(a, fn+8) == original
        target = bl_target(m, site)
        assert target != fn and target != original
        merged[off(m,site):off(m,site)+4] = a64_branch(site,fn,True)
        p = off(bytes(merged),fn+8)
        merged[p:p+4] = a64_branch(fn+8,target,True)
        chains.append(dict(site=hex(site),aspect=hex(fn),main_chain=hex(target),old_chain=hex(original)))
    # Preserve the frozen research build identity for byte-identical replay.
    for old, new in IDENTITY_EDITS:
        needle = bytes.fromhex(old)
        assert merged.count(needle) == 1
        p = merged.index(needle)
        assert 98893824 <= p < len(m)
        merged[p:p+32] = bytes.fromhex(new)
    data = bytes(merged); er = elf(data)
    assert er.get_section_by_name('.rela.dyn')['sh_size'] == rm['sh_size']+96
    assert next(t['d_val'] for t in er.get_section_by_name('.dynamic').iter_tags() if t['d_tag']=='DT_RELASZ') == rm['sh_size']+96
    # Every original LOAD retains its memory permissions and extent.
    mainloads = [dict(s.header) for s in em.iter_segments() if s['p_type']=='PT_LOAD']
    loads = [dict(s.header) for s in er.iter_segments() if s['p_type']=='PT_LOAD']
    assert loads[:len(mainloads)] == mainloads
    spans = sorted((s['p_vaddr'],s['p_vaddr']+s['p_memsz']) for s in loads)
    assert all(p[1] <= q[0] for p,q in zip(spans,spans[1:]))
    check_hash(data, LAYOUT["output_AP"], "combined AP")
    return data


def compile_cp(source, gcc):
    check_hash(source, LAYOUT['input_CP'], 'main CP')
    check_hash(Path(gcc).read_bytes(), LAYOUT['compiler_sha256'], 'compiler')
    for item in LAYOUT['source_files']:
        check_hash((ROOT/item['path']).read_bytes(), item['sha256'], item['path'])
    with tempfile.TemporaryDirectory(prefix='a7m4-feature_integration-') as directory:
        return _compile_cp(source, str(gcc), Path(directory))


def _compile_cp(raw, compiler, out):
    cpdir = ROOT/'native/feature-integration/cp'
    sources = [cpdir/name for name in ('crop_core.c', 'cp_selector.c', 'cp_selector_wrapper.S',
               'cp_capture_latch.c', 'cp_crop_wrappers.S', 'aspect_gate.S', 'aspect_prepare.S', 'boot_wrapper.S')]
    linker = cpdir/'aspect.ld'
    flags = ['-mcpu=cortex-a5', '-mthumb', '-mfloat-abi=soft', '-Os', '-std=c11',
             '-Wall', '-Wextra', '-Werror', '-ffreestanding', '-fno-builtin',
             '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
             '-ffunction-sections', '-fdata-sections']
    objects, commands = [], []
    for i, path in enumerate(sources):
        obj = out / f'input_{i}.o'
        mode = '-marm' if path.name == 'boot_wrapper.S' else '-mthumb'
        cmd = [compiler, *flags, mode, '-c', str(path), '-o', str(obj)]
        result = subprocess.run(cmd, capture_output=True)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        objects.append(obj)
        commands.append(cmd)
    elf_path = out / 'aspect.elf'
    cmd = [compiler, '-mcpu=cortex-a5', '-mthumb', '-mfloat-abi=soft', '-nostdlib',
           '-Wl,--build-id=none', '-Wl,-T,' + str(linker), *map(str, objects), '-o', str(elf_path)]
    result = subprocess.run(cmd, capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    commands.append(cmd)
    elf = ELFFile(BytesIO(elf_path.read_bytes()))
    syms = list(elf.get_section_by_name('.symtab').iter_symbols())
    assert not [s.name for s in syms if s.name and s['st_shndx'] == 'SHN_UNDEF']
    symbols = {s.name: int(s['st_value']) for s in syms if s.name and not s.name.startswith('$')}
    data = bytearray(raw)
    edits = []

    def edit(va, block, reason):
        at = va - BASE
        assert not any(at < r['offset']+r['bytes'] and r['offset'] < at+len(block) for r in edits)
        before = raw[at:at+len(block)]
        assert len(before) == len(block)
        data[at:at+len(block)] = block
        edits.append(dict(VA=hex(va), offset=at, bytes=len(block), reason=reason,
                          before_sha256=hashlib.sha256(before).hexdigest(),
                          after_sha256=hashlib.sha256(block).hexdigest()))

    sections = []
    for sec in elf.iter_sections():
        if sec['sh_flags'] & 2 and sec['sh_size']:
            sections.append(dict(name=sec.name, VA=hex(sec['sh_addr']), bytes=sec['sh_size'], type=sec['sh_type']))
            if sec['sh_type'] != 'SHT_NOBITS':
                edit(sec['sh_addr'], sec.data(), 'Merged ' + sec.name)
    assert symbols['nt_late_boot'] == 0xba5740
    # The current native checker remains byte-identical except for its pinned
    # whole-prefix CRC literal, now also covering the new executable pages.
    old_crc = zlib.crc32(raw[0x118000-BASE:0x11e000-BASE])
    assert old_crc == 0xb195a526
    assert raw[0xba4dc4-BASE:0xba4dc8-BASE] == struct.pack('<I', old_crc)
    crc = zlib.crc32(data[0x118000-BASE:0x11e000-BASE])
    edit(0xba4dc4, struct.pack('<I', crc), 'Same native preflight with combined prefix CRC')
    sites = [3170762, 10504624, 10498370, 4215066, 10539026, 10539100, 10539610, 10539240, 4212274, 4197926, 10510724, 4147784]
    for site in sites:
        edit(site, thumb_branch(site, symbols["aspect_resident_gate"], True), "Guarded aspect adapter")
    assert len(sites) == 12 and len(data) == len(raw)
    cursor = 0
    for row in sorted(edits, key=lambda r: r['offset']):
        at = row['offset']
        assert data[cursor:at] == raw[cursor:at]
        cursor = at + row['bytes']
    assert data[cursor:] == raw[cursor:]
    assert data[0x118000-BASE:0x11a4a4-BASE] == raw[0x118000-BASE:0x11a4a4-BASE]
    assert data[0x11e000-BASE:0x120000-BASE] == raw[0x11e000-BASE:0x120000-BASE]
    check_hash(data, LAYOUT["output_CP"], "combined CP")
    return bytes(data)


def parse(b):
    assert b[:4]==b'uxc\7';count,rem=divmod(struct.unpack_from('<I',b,12)[0],0x1001);assert not rem
    base=(16+2*count+3)&~3;idbase=0x1e000000+(struct.unpack_from('<H',b,10)[0]<<13);rows={}
    for i in range(count):
        off=struct.unpack_from('<H',b,16+2*i)[0]
        if off==65535:continue
        p=base+4*off;rid=struct.unpack_from('<I',b,p)[0];assert rid==idbase+i
        rows[rid-0x1c000000]=b[p+4:b.index(0,p+4)].decode('utf8')
    return rows

def merge_string(base,main,aspect):
    a,b,c=map(parse,(base,main,aspect));updates={k:v for k,v in c.items() if a.get(k)!=v}
    for i in range(4):
        old,new=0x200ab60+i,0x200ab4c+i
        assert updates[old]==('17:6','65:24','5:4','7:6')[i]
        assert b.get(new) in (None,'') and c.get(new) in (None,'')
        updates[new]=updates.pop(old)
    assert set(a)<=set(c)
    count,rem=divmod(struct.unpack_from('<I',main,12)[0],0x1001);assert not rem
    data_base=(16+2*count+3)&~3;idbase=0x1e000000+(struct.unpack_from('<H',main,10)[0]<<13)
    for rid,value in updates.items():
        assert rid not in b or b[rid]==a.get(rid) or b[rid]==value or (0x200ab4c<=rid<=0x200ab4f and b[rid]==''),(hex(rid),b.get(rid),value)
    # Repack live records, eliminating obsolete append-only sound/LUT records.
    # This keeps 16-bit word offsets within range even for Hindi/Thai banks.
    expected=b|updates;out=bytearray(main[:data_base]);out[16:16+count*2]=b'\xff\xff'*count
    # The index addresses record starts, not file size. Put the longest
    # record last so its payload may extend past the last u16 word offset.
    ordered=sorted(expected.items(),key=lambda item:len(item[1].encode('utf8')))
    for rid,value in ordered:
        index=rid+0x1c000000-idbase;assert 0<=index<count
        out.extend(bytes(-len(out)%4));position=len(out);word=(position-data_base)//4;assert word<65535,(hex(rid),word)
        out.extend(struct.pack('<I',rid+0x1c000000)+value.encode('utf8')+b'\0');out.extend(bytes(-len(out)%4))
        struct.pack_into('<H',out,16+index*2,word)
    assert parse(bytes(out))==expected
    return bytes(out),{hex(k):v for k,v in updates.items()}

def compose_string(name, base, main, aspect):
    expected = LAYOUT['resource_banks'][name]
    for data, key in ((base, 'common_sha256'), (main, 'source_sha256'), (aspect, 'aspect_sha256')):
        check_hash(data, expected[key], name + ' ' + key)
    result, _ = merge_string(base, main, aspect)
    check_hash(result, expected['output_sha256'], name + ' result')
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='kind', required=True)
    ap = subs.add_parser('ap')
    for name in ('base', 'main', 'aspect'):
        ap.add_argument('--' + name, type=Path, required=True)
    cp = subs.add_parser('cp')
    cp.add_argument('--main', type=Path, required=True)
    cp.add_argument('--gcc', type=Path, required=True)
    bank = subs.add_parser('string')
    bank.add_argument('--name', choices=sorted(LAYOUT['resource_banks']), required=True)
    for name in ('base', 'main', 'aspect'):
        bank.add_argument('--' + name, type=Path, required=True)
    for sub in (ap, cp, bank):
        sub.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; use a new path')
    if args.kind == 'cp':
        data = compile_cp(args.main.read_bytes(), args.gcc)
    elif args.kind == 'ap':
        data = compose_ap(args.base.read_bytes(), args.main.read_bytes(), args.aspect.read_bytes())
    else:
        data = compose_string(args.name, args.base.read_bytes(), args.main.read_bytes(), args.aspect.read_bytes())
    write_new(args.output, data)
    print(json.dumps({'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}))


if __name__ == '__main__':
    main()
