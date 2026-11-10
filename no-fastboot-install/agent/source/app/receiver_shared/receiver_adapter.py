from __future__ import annotations
from product_integrity import pinned, state_path
import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
BASE = CASE.parent
ADAPTER = BASE / 'container'
DAT_PROFILE = BASE / 'profiles/profile.json'
FROZEN = {'app/container/updater.py': pinned('app/container/updater.py'), 'app/container/common.py': pinned('app/container/common.py'), 'app/container/m4_profile.json': pinned('app/container/m4_profile.json'), 'app/profiles/profile.json': pinned('app/profiles/profile.json')}

def check_frozen():
    for relative, expected in FROZEN.items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            raise ValueError('Frozen dependency is not a workspace regular file')
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError('Frozen dependency changed: ' + relative)
check_frozen()
sys.path[:0] = [str(ADAPTER), str(ROOT / 'vendor/python'), str(ROOT / 'vendor/squashfs'), str(ROOT / 'vendor')]
from common import file_sha, local_path, locked, new_dir, require, sha
from elftools.elf.elffile import ELFFile
PROFILE = json.loads(DAT_PROFILE.read_text('utf-8'))
P1_BYTES = 25100288
FAT_BYTES = 19377152
MAX_WINDOW = 16384
SCHEMA = 'm4-receiver-boolfix-bundle/1'
PATCH_SET = 'sd-version-bool0-to-bool1'
BAD_STATE = 'user_key_legacy_version_false'
GOOD_STATE = 'user_key_version_true'
SD_NAME = 'usr/lib/libsdfileinputupdaterapi.so'
CC_NAME = 'usr/lib/libupdatercorecommon.so'
SD_BAD_SHA = 'cd6fe3329f05e62e654b96d075e69f9ece12f1f84c49d28953fd9c4ea2d224df'
SD_GOOD_SHA = '48846e295f4d46705252f9901777aac383b02c41d14c0512c45388139dea3ccb'
CC_SHA = 'cfe23b709f1a4feba16642729f39c9bb5f4516caa188fa67a6d31d3c1d833425'
KEY_SHA = 'c39f3d878e129bbac87ad346182df754d7dd99d80c35c38bbb6517e37ca8e449'
ZERO = bytes.fromhex('00008052c0035fd6')
ONE = bytes.fromhex('20008052c0035fd6')
VERIFY_KEY = '_ZN7Updater21SignatureVerification9verifyKeyEPKc'
spec = importlib.util.spec_from_file_location('_m4_receiver_boolfix_fat_helper', ADAPTER / 'updater.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.PROFILE = PROFILE
helper.SD_GATE = PROFILE['sd_signature_gate']
helper.SD_VER_GATE = PROFILE['sd_version_gate']
helper.CHK_GATE = PROFILE['chkfirm_version_gate']

def save_json(path, value):
    with local_path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')

def source_pins():
    check_frozen()
    own = str(Path(__file__).resolve().relative_to(ROOT)).replace('\\', '/')
    return {**FROZEN, own: file_sha(Path(__file__))}

def symbol_offset(elf, symbol, va, size=None):
    rows = [s for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name == symbol and s['st_shndx'] != 'SHN_UNDEF']
    require(len(rows) == 1 and rows[0]['st_value'] == va and (size is None or rows[0]['st_size'] == size), 'Symbol address/size differs: ' + symbol)
    count = size if size is not None else 8
    segs = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] <= va and (va + count <= s['p_vaddr'] + s['p_filesz'])]
    require(len(segs) == 1 and segs[0]['p_flags'] & 1, 'Executable symbol mapping differs')
    return segs[0]['p_offset'] + va - segs[0]['p_vaddr']

def check_vtable(elf):
    targets = []
    for section in elf.iter_sections():
        if section['sh_type'] != 'SHT_RELA':
            continue
        symbols = elf.get_section(section['sh_link'])
        for relocation in section.iter_relocations():
            if relocation['r_offset'] != 121920:
                continue
            symbol = symbols.get_symbol(relocation['r_info_sym'])
            if relocation['r_info_type'] == 1027:
                value = relocation['r_addend']
            else:
                require(symbol['st_shndx'] != 'SHN_UNDEF', 'Undefined predicate vtable target')
                value = symbol['st_value'] + relocation['r_addend']
            targets.append(value)
    require(targets == [40916], 'Version vtable no longer targets the verified predicate')

def library_state(data, entry):
    digest = sha(data)
    is_sd = entry == PROFILE['libraries']['libsdfileinputupdaterapi.so']
    require(digest in ({SD_BAD_SHA, SD_GOOD_SHA} if is_sd else {entry['patched_sha256']}), 'Unreviewed receiver library; no migration allowed')
    elf = ELFFile(io.BytesIO(data))
    require(elf.elfclass == 64 and elf.little_endian and (elf['e_machine'] == 'EM_AARCH64'), 'Expected M4 AArch64 ELF')
    offset = symbol_offset(elf, VERIFY_KEY, entry['va'])
    require(offset == entry['offset'] and data[offset:offset + 8] == ZERO, 'Existing verifyKey differs')
    report = dict(sha256=digest, bytes=len(data), symbol=VERIFY_KEY, va=entry['va'], file_offset=offset, entry_hex=ZERO.hex(), patched=True, signature_bypass=False)
    if is_sd:
        signature, version = (PROFILE['sd_signature_gate'], PROFILE['sd_version_gate'])
        sigoff = symbol_offset(elf, signature['symbol'], signature['va'], signature['size'])
        veroff = symbol_offset(elf, version['symbol'], version['va'], version['size'])
        require(sigoff == 44016 and veroff == 40916, 'SD gate mapping differs')
        require(data[sigoff:sigoff + 8] == ZERO, 'Signature success status must remain zero')
        good = digest == SD_GOOD_SHA
        require(data[veroff:veroff + 8] == (ONE if good else ZERO), 'Predicate entry differs from known state')
        call = bytes.fromhex(version['caller_hex'])
        require(data[version['caller_va']:version['caller_va'] + len(call)] == call, 'Boolean predicate caller changed')
        caller = signature['caller']
        require(data[caller['va']:caller['va'] + 4].hex() == caller['call_hex'] and data[caller['result_va']:caller['result_va'] + 4].hex() == caller['result_hex'], 'Signature caller changed')
        check_vtable(elf)
        report.update(signature_bypass=True, version_bypass=True, signature_function=dict(va=sigoff, return_value=0), version_function=dict(va=veroff, return_value=1 if good else 0), boolean_caller_verified=True, version_vtable_verified=True)
    return report
helper.library_state = library_state

def inspect_bytes(raw):
    require(len(raw) == P1_BYTES, 'Receiver requires full 25100288-byte p1; packaged volumes are forbidden')
    report, fat, initrd, inventory, contents, links = helper.inspect_bytes(raw)
    require(fat.sector_size * fat.total_sectors == FAT_BYTES and report['fat_bytes'] == FAT_BYTES, 'FAT geometry changed')
    require(report['key_sha256'] == KEY_SHA, 'Unreviewed receiver public key')
    require(sha(contents[CC_NAME]) == CC_SHA and report['chkfirm_version_gate']['patched'], 'Receiver must retain the known core comparison gates')
    require(all((v['patched'] for v in report['libraries'].values())), 'Mixed verifyKey baseline')
    sd = report['libraries']['libsdfileinputupdaterapi.so']
    good = sd['sha256'] == SD_GOOD_SHA
    sd['version_gate_modified'] = sd.pop('version_bypass')
    sd['version_condition_forced_true'] = good
    report.update(schema='m4-receiver-boolfix-state/1', trust_state=GOOD_STATE if good else BAD_STATE, version_boolean_return=1 if good else 0, signature_success_status=0, known_bad_version_boolean=not good, current_body_verified=False, partition_tail_sha256=sha(raw[FAT_BYTES:]), partition_tail_bytes=P1_BYTES - FAT_BYTES, device_file_sha256={name: report['files'][name] for name in ('dat1', 'dat2', 'dat3', 'dat4') if name in report['files']})
    return (report, fat, initrd, inventory, contents, links)

def allowed_regions(fat):
    stream = fat.get('boot/initrd.img').open()
    allocated = sum((count * stream.block_size for _, count in stream._runlist))
    spans = [(a, n, 'initrd existing allocation') for a, _, n in helper.map_range(fat, stream, 0, allocated)]
    sums = fat.get('p1chksum').open()
    spans += [(a, n, 'p1chksum') for a, _, n in helper.map_range(fat, sums, 0, len(sums.read()))]
    boot = fat.get('boot').open()
    directory = boot.read()
    entries = [i for i in range(0, len(directory) - 31, 32) if directory[i:i + 11] == b'INITRD  IMG']
    require(len(entries) == 1, 'Ambiguous initrd FAT directory entry')
    sizeoff = entries[0] + 28
    spans += [(a, n, 'initrd FAT size') for a, _, n in helper.map_range(fat, boot, sizeoff, 4)]
    cursor = 0
    for start, length, _ in sorted(spans):
        require(cursor <= start < start + length <= FAT_BYTES, 'Invalid or overlapping FAT allocation spans')
        cursor = start + length
    return sorted(spans)

def windowdiff(old, new, spans):
    windows = []
    for row in spans:
        start, length = (row['offset'], row['length'])
        for offset in range(start, start + length, MAX_WINDOW):
            count = min(MAX_WINDOW, start + length - offset)
            a, b = (old[offset:offset + count], new[offset:offset + count])
            if a != b:
                windows.append(dict(offset=offset, length=count, before_sha256=sha(a), after_sha256=sha(b)))
    require(0 < len(windows) <= 768 and sum((2 * r['length'] for r in windows)) <= 24 * 1024 * 1024, 'Migration exceeds reviewed fixed-writer bounds')
    return windows

def verify_patch_semantics(old, new):
    before, fat, initrd, inventory, contents, links = inspect_bytes(old)
    after, _, new_initrd, new_inventory, new_contents, new_links = inspect_bytes(new)
    require(before['trust_state'] == BAD_STATE and after['trust_state'] == GOOD_STATE, 'Only known false-to-true receiver migration is supported')
    require(old[FAT_BYTES:] == new[FAT_BYTES:], 'Physical partition tail changed')
    expected_sd = bytearray(contents[SD_NAME])
    require(expected_sd[40916:40924] == ZERO, 'Original version entry is not known false')
    expected_sd[40916:40924] = ONE
    require(sha(expected_sd) == SD_GOOD_SHA, 'Unexpected fixed SD hash')
    require(new_contents == {**contents, SD_NAME: bytes(expected_sd)}, 'Change outside the one SD Boolean entry')
    expected_inventory = copy.deepcopy(inventory)
    expected_inventory[SD_NAME].update(bytes=len(expected_sd), sha256=sha(expected_sd))
    require(new_inventory == expected_inventory and new_links == links, 'SquashFS metadata or links changed')
    require(contents['etc/VerificationKey.pem'] == new_contents['etc/VerificationKey.pem'], 'Public key changed')
    keep = lambda r: {name: digest for name, digest in r['files'].items() if name not in ('boot/initrd.img', 'p1chksum')}
    require(keep(before) == keep(after), 'Device/other FAT files changed')
    spans, cursor = ([], 0)
    for start, length, purpose in allowed_regions(fat):
        require(old[cursor:start] == new[cursor:start], 'FAT metadata/content changed outside allowed allocation')
        spans.append(dict(offset=start, length=length, purpose=purpose, before_sha256=sha(old[start:start + length]), after_sha256=sha(new[start:start + length])))
        cursor = start + length
    require(old[cursor:] == new[cursor:], 'Partition changed outside allowed FAT regions')
    windows = windowdiff(old, new, spans)
    return dict(schema='m4-receiver-boolfix-semantics/1', patch_set=PATCH_SET, before=before, after=after, bytes=P1_BYTES, source_sha256=sha(old), candidate_sha256=sha(new), spans=spans, windows=windows, changed_bytes=sum((a != b for a, b in zip(old, new))), window_count=len(windows), stage_bytes=sum((2 * r['length'] for r in windows)), outside_spans_unchanged=True, partition_tail_unchanged=True, only_library_bytes_changed=[dict(member=SD_NAME, offset=40916, before_hex=ZERO.hex(), after_hex=ONE.hex())], all_other_contents_metadata_links_unchanged=True, public_key_unchanged=True, verifyKey_unchanged=True, signature_gate_unchanged=True, core_gates_unchanged=True, device_files_unchanged=True, hardware_operations=0)

def prepare(source, expected_sha256, output):
    pins = source_pins()
    path = locked(source, expected_sha256)
    raw = path.read_bytes()
    before, fat, initrd, inventory, contents, links = inspect_bytes(raw)
    require(before['trust_state'] == BAD_STATE, 'Input is not the known bad receiver state')
    output = new_dir(output)
    work = new_dir(output / 'work')
    changed_sd = bytearray(contents[SD_NAME])
    changed_sd[40916:40924] = ONE
    require(sha(changed_sd) == SD_GOOD_SHA, 'Wrong Boolean candidate')
    rebuilt = helper.rebuild_initrd(initrd, {SD_NAME: bytes(changed_sd)}, work)
    result = bytearray(raw)

    def put(stream, offset, value):
        for disk, start, count in helper.map_range(fat, stream, offset, len(value)):
            require(0 <= disk < disk + count <= FAT_BYTES, 'Write outside existing FAT image')
            result[disk:disk + count] = value[start:start + count]
    stream = fat.get('boot/initrd.img').open()
    allocated = sum((count * stream.block_size for _, count in stream._runlist))
    require(len(rebuilt) <= allocated, 'Rebuilt initrd exceeds existing allocation; relocation forbidden')
    put(stream, 0, rebuilt + bytes(allocated - len(rebuilt)))
    boot = fat.get('boot').open()
    directory = boot.read()
    entries = [i for i in range(0, len(directory) - 31, 32) if directory[i:i + 11] == b'INITRD  IMG']
    require(len(entries) == 1, 'Ambiguous initrd FAT entry')
    offset = entries[0] + 28
    require(struct.unpack_from('<I', directory, offset)[0] == len(initrd), 'Original initrd size differs')
    put(boot, offset, struct.pack('<I', len(rebuilt)))
    sums = fat.get('p1chksum').open()
    old_sum = sums.read()
    new_sum = old_sum.replace(hashlib.md5(initrd).hexdigest().encode(), hashlib.md5(rebuilt).hexdigest().encode())
    require(len(old_sum) == len(new_sum) and old_sum != new_sum, 'p1chksum update failed')
    put(sums, 0, new_sum)
    candidate = bytes(result)
    semantics = verify_patch_semantics(raw, candidate)
    require(file_sha(path) == expected_sha256.lower(), 'Input changed during preparation')
    require(source_pins() == pins, 'Adapter dependencies changed during preparation')
    (output / 'p1_original.bin').write_bytes(raw)
    (output / 'p1_candidate.bin').write_bytes(candidate)
    manifest = {**semantics, 'schema': SCHEMA, 'original': 'p1_original.bin', 'candidate': 'p1_candidate.bin', 'source': str(path), 'key_sha256': KEY_SHA, 'adapter_sources': pins, 'status': 'OFFLINE_MIGRATION_BUNDLE_NOT_BODY_BOUND', 'current_body_verified': False, 'restore_role': 'rollback_to_saved_known_bad_version_false', 'no_packaged_image_transplant': True, 'no_partition_allocation_change': True}
    save_json(output / 'bundle.json', manifest)
    return manifest

def load_bundle(directory):
    directory = local_path(directory)
    manifest = json.loads(local_path(directory / 'bundle.json', existing=True).read_text('utf-8-sig'))
    require(manifest['schema'] == SCHEMA and manifest['patch_set'] == PATCH_SET and (manifest['original'] == 'p1_original.bin') and (manifest['candidate'] == 'p1_candidate.bin') and (manifest['bytes'] == P1_BYTES) and (manifest['adapter_sources'] == source_pins()), 'Wrong/unbound receiver migration bundle')
    old = locked(directory / 'p1_original.bin', manifest['source_sha256']).read_bytes()
    new = locked(directory / 'p1_candidate.bin', manifest['candidate_sha256']).read_bytes()
    check = verify_patch_semantics(old, new)
    for key, value in check.items():
        if key != 'schema':
            require(manifest.get(key) == value, 'Bundle semantic evidence differs: ' + key)
    require(manifest['key_sha256'] == KEY_SHA, 'Bundle public key differs')
    return (manifest, old, new)

def replay(bundle, current, expected, direction, output):
    manifest, old, new = load_bundle(bundle)
    require(direction in ('apply', 'restore'), 'Unsupported replay direction')
    path = locked(current, expected)
    actual = path.read_bytes()
    current_state = inspect_bytes(actual)[0]
    before, after = (old, new) if direction == 'apply' else (new, old)
    already_restored = direction == 'restore' and all((actual[r['offset']:r['offset'] + r['length']] == old[r['offset']:r['offset'] + r['length']] for r in manifest['spans']))
    if direction == 'apply':
        require(sha(actual) == manifest['source_sha256'] and current_state['trust_state'] == BAD_STATE, 'Apply requires the exact full source hash and known false state')
    else:
        require(current_state['trust_state'] == (BAD_STATE if already_restored else GOOD_STATE), 'Restore source is neither complete candidate nor already-restored original state')
    for row in manifest['spans']:
        start, length = (row['offset'], row['length'])
        require(already_restored or actual[start:start + length] == before[start:start + length], 'Migration window changed; mixed/unknown state must stop')
    result = bytearray(actual)
    if not already_restored:
        for row in manifest['spans']:
            start, length = (row['offset'], row['length'])
            result[start:start + length] = after[start:start + length]
    result = bytes(result)
    result_state = inspect_bytes(result)[0]
    require(result_state['trust_state'] == (GOOD_STATE if direction == 'apply' else BAD_STATE), 'Replay target state differs')
    cursor = 0
    for row in manifest['spans']:
        start, length = (row['offset'], row['length'])
        require(actual[cursor:start] == result[cursor:start], 'Replay modified outside saved windows')
        cursor = start + length
    require(actual[cursor:] == result[cursor:], 'Replay modified tail/outside windows')
    require(file_sha(path) == expected.lower(), 'Replay source changed')
    output = new_dir(output)
    target = output / ('p1_' + direction + '.bin')
    target.write_bytes(result)
    receipt = dict(schema='m4-receiver-boolfix-replay/1', patch_set=PATCH_SET, direction=direction, input_sha256=sha(actual), output_sha256=sha(result), bytes=P1_BYTES, checked_windows=len(manifest['spans']), outside_windows_preserved=True, exact_original_restored=result == old, already_restored=already_restored, before_state=current_state['trust_state'], after_state=result_state['trust_state'], restore_role=manifest['restore_role'] if direction == 'restore' else None, status='LOCAL_FILE_REPLAY_ONLY', current_body_verified=False, camera_io=False, hardware_operations=0)
    save_json(output / 'receipt.json', receipt)
    return receipt
