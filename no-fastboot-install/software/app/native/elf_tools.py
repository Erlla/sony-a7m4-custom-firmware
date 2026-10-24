from product_integrity import pinned, state_path
from pathlib import Path
import argparse
import hashlib
import json
import secrets
import subprocess
import sys
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vendor/python'))
from elftools.elf.elffile import ELFFile

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inspect(path, executable):
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        assert elf['e_machine'] == 'EM_AARCH64'
        assert elf['e_type'] == ('ET_EXEC' if executable else 'ET_DYN')
        assert not any((p['p_type'] == 'PT_INTERP' for p in elf.iter_segments()))
        deps, imports, relocations, init = ([], [], [], None)
        for section in elf.iter_sections():
            if section['sh_type'] == 'SHT_DYNAMIC':
                for tag in section.iter_tags():
                    if tag.entry.d_tag == 'DT_NEEDED':
                        deps.append(tag.needed)
                    if tag.entry.d_tag == 'DT_INIT':
                        init = tag.entry.d_val
                    assert tag.entry.d_tag != 'DT_TEXTREL'
            if section['sh_type'] == 'SHT_DYNSYM':
                imports += [s.name for s in section.iter_symbols() if s['st_shndx'] == 'SHN_UNDEF' and s.name]
            if section['sh_type'] in ('SHT_RELA', 'SHT_REL'):
                relocations += [r.entry.r_info_type for r in section.iter_relocations()]
        assert not deps and (not imports)
        assert all((t == 1027 for t in relocations)), relocations
        if not executable:
            assert init is not None
        return {'elf_type': elf['e_type'], 'entry': elf['e_entry'], 'dt_init': init, 'bytes': path.stat().st_size, 'sha256': sha(path), 'dependencies': deps, 'undefined_imports': imports, 'relative_relocations': len(relocations), 'segments': [{'type': s['p_type'], 'flags': s['p_flags'], 'offset': s['p_offset'], 'vaddr': s['p_vaddr'], 'filesz': s['p_filesz'], 'memsz': s['p_memsz']} for s in elf.iter_segments()]}
