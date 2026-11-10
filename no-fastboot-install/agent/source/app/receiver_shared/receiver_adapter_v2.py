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
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
V1_PATH = CASE / 'receiver_adapter.py'
V1_SHA = pinned('app/receiver_shared/receiver_adapter.py')
with V1_PATH.open('rb') as stream:
    if hashlib.file_digest(stream, 'sha256').hexdigest() != V1_SHA:
        raise ValueError('Frozen historical adapter source changed')
spec = importlib.util.spec_from_file_location('_m4_current_receiver_low_level', V1_PATH)
low = importlib.util.module_from_spec(spec)
spec.loader.exec_module(low)
helper, PROFILE = (low.helper, low.PROFILE)
require, sha, file_sha, locked, new_dir, local_path = (low.require, low.sha, low.file_sha, low.locked, low.new_dir, low.local_path)
save_json, allowed_regions, windowdiff = (low.save_json, low.allowed_regions, low.windowdiff)
P1_BYTES, FAT_BYTES, MAX_WINDOW = (low.P1_BYTES, low.FAT_BYTES, low.MAX_WINDOW)
SD_NAME, CC_NAME, KEY_SHA = (low.SD_NAME, low.CC_NAME, low.KEY_SHA)
ZERO, ONE = (low.ZERO, low.ONE)
SCHEMA = 'm4-receiver-boolfix-bundle/2'
PATCH_SET = 'sd-signature-version-bool1-and-core-gates/1'
SOURCE_STATES = ('user_key_gate',)
GOOD_STATE = 'user_key_version_true'
SOURCE_P1_SHA = '97ab1b843e3b8fecadf68c1b7d72362cc4ea5a432d1c15f2502498060793d9ea'
SD_SOURCE_SHA = '0624862064e43495d6291637d2e193d4656145d069550c58a4ce184bb9f5e354'
SD_GOOD_SHA = low.SD_GOOD_SHA
CC_SOURCE_SHA = 'b2b066b963a42d96556f811a773579eb16a0358de1b3a9206a1845c0df99bb74'
CC_GOOD_SHA = low.CC_SHA
RESTORE_ROLE = 'rollback_to_saved_original_user_key_gate'

def source_pins():
    require(file_sha(V1_PATH) == V1_SHA, 'Frozen low-level adapter changed')
    return {**low.source_pins(), str(Path(__file__).resolve().relative_to(ROOT)).replace('\\', '/'): file_sha(Path(__file__))}

def library_state(data, entry):
    digest = sha(data)
    is_sd = entry == PROFILE['libraries']['libsdfileinputupdaterapi.so']
    require(digest in ({SD_SOURCE_SHA, SD_GOOD_SHA} if is_sd else {entry['patched_sha256']}), 'Unknown current-receiver library; historical bool0 is not a v2 source')
    elf = low.ELFFile(io.BytesIO(data))
    require(elf.elfclass == 64 and elf.little_endian and (elf['e_machine'] == 'EM_AARCH64'), 'M4 AArch64 ELF required')
    offset = low.symbol_offset(elf, low.VERIFY_KEY, entry['va'])
    require(offset == entry['offset'] and data[offset:offset + 8] == ZERO, 'Existing user verifyKey gate changed')
    report = dict(sha256=digest, bytes=len(data), symbol=low.VERIFY_KEY, va=entry['va'], file_offset=offset, entry_hex=ZERO.hex(), patched=True, signature_bypass=False)
    if is_sd:
        good = digest == SD_GOOD_SHA
        signature, version = (PROFILE['sd_signature_gate'], PROFILE['sd_version_gate'])
        sigoff = low.symbol_offset(elf, signature['symbol'], signature['va'], signature['size'])
        veroff = low.symbol_offset(elf, version['symbol'], version['va'], version['size'])
        require(sigoff == 44016 and veroff == 40916, 'SD gate mapping differs')
        require(data[sigoff:sigoff + 8] == (ZERO if good else bytes.fromhex(signature['original_hex'])), 'Wrong signature state')
        require(data[veroff:veroff + 8] == (ONE if good else bytes.fromhex(version['original_hex'])), 'Wrong version predicate state')
        caller = signature['caller']
        require(data[caller['va']:caller['va'] + 4].hex() == caller['call_hex'] and data[caller['result_va']:caller['result_va'] + 4].hex() == caller['result_hex'], 'Signature caller differs')
        call = bytes.fromhex(version['caller_hex'])
        require(data[version['caller_va']:version['caller_va'] + len(call)] == call, 'Boolean caller differs')
        low.check_vtable(elf)
        report.update(signature_bypass=good, version_bypass=good, signature_function=dict(va=sigoff, return_value=0 if good else None), version_function=dict(va=veroff, return_value=1 if good else None), boolean_caller_verified=True, version_vtable_verified=True)
    return report
helper.library_state = library_state

def inspect_bytes(raw):
    require(len(raw) == P1_BYTES, 'Receiver v2 requires full 25100288-byte p1; packaged volumes forbidden')
    report, fat, initrd, inventory, contents, links = helper.inspect_bytes(raw)
    require(fat.sector_size * fat.total_sectors == FAT_BYTES and report['key_sha256'] == KEY_SHA, 'FAT geometry or existing public key differs')
    require(all((v['patched'] for v in report['libraries'].values())), 'Existing four verifyKey entries must remain')
    sd = report['libraries']['libsdfileinputupdaterapi.so']
    good = sd['sha256'] == SD_GOOD_SHA
    require(sha(contents[CC_NAME]) == (CC_GOOD_SHA if good else CC_SOURCE_SHA), 'Mixed or unreviewed SD/core gate state')
    sd['version_gate_modified'] = sd.pop('version_bypass')
    sd['version_condition_forced_true'] = good
    report.update(schema='m4-current-receiver-state/2', trust_state=GOOD_STATE if good else 'user_key_gate', version_boolean_return=1 if good else None, version_predicate_mode='forced_true' if good else 'original_version_comparison', signature_success_status=0, signature_gate_forced_success=good, known_bad_version_boolean=False, current_body_verified=False, partition_tail_sha256=sha(raw[FAT_BYTES:]), partition_tail_bytes=P1_BYTES - FAT_BYTES, device_file_sha256={n: report['files'][n] for n in ('dat1', 'dat2', 'dat3', 'dat4') if n in report['files']})
    return (report, fat, initrd, inventory, contents, links)

def expected_libraries(contents):
    sd = bytearray(contents[SD_NAME])
    require(sha(sd) == SD_SOURCE_SHA, 'Only the current original user SD library is accepted')
    sd[44016:44024] = ZERO
    sd[40916:40924] = ONE
    require(sha(sd) == SD_GOOD_SHA, 'Wrong corrected SD library hash')
    cc = bytearray(contents[CC_NAME])
    require(sha(cc) == CC_SOURCE_SHA, 'Only original current core library is accepted')
    for site in PROFILE['chkfirm_version_gate']['sites']:
        offset, size = (site['offset'], site['length'])
        require(cc[offset:offset + size].hex() == site['original_hex'], 'Core source entry differs')
        cc[offset:offset + size] = bytes.fromhex(site['patched_hex'])
    require(sha(cc) == CC_GOOD_SHA, 'Wrong corrected core library hash')
    return {SD_NAME: bytes(sd), CC_NAME: bytes(cc)}

def verify_patch_semantics(old, new):
    require(sha(old) == SOURCE_P1_SHA, 'Source is not the explicitly read current full p1')
    before, fat, _, inventory, contents, links = inspect_bytes(old)
    after, _, _, new_inventory, new_contents, new_links = inspect_bytes(new)
    require(before['trust_state'] in SOURCE_STATES and after['trust_state'] == GOOD_STATE, 'Wrong v2 state transition')
    require(old[FAT_BYTES:] == new[FAT_BYTES:], 'Physical partition tail changed')
    replacements = expected_libraries(contents)
    require(new_contents == {**contents, **replacements}, 'Unexpected initrd content change')
    expected_inventory = copy.deepcopy(inventory)
    for name, value in replacements.items():
        expected_inventory[name].update(bytes=len(value), sha256=sha(value))
    require(new_inventory == expected_inventory and new_links == links, 'SquashFS metadata/links changed')
    require(contents['etc/VerificationKey.pem'] == new_contents['etc/VerificationKey.pem'], 'Existing public key changed')
    keep = lambda r: {n: h for n, h in r['files'].items() if n not in ('boot/initrd.img', 'p1chksum')}
    require(keep(before) == keep(after), 'Device state or other FAT file changed')
    spans, cursor = ([], 0)
    for start, length, purpose in allowed_regions(fat):
        require(old[cursor:start] == new[cursor:start], 'Change outside existing FAT allocation')
        spans.append(dict(offset=start, length=length, purpose=purpose, before_sha256=sha(old[start:start + length]), after_sha256=sha(new[start:start + length])))
        cursor = start + length
    require(old[cursor:] == new[cursor:], 'Outside-span content or tail changed')
    windows = windowdiff(old, new, spans)
    patches = [dict(member=SD_NAME, offset=44016, before_hex=PROFILE['sd_signature_gate']['original_hex'], after_hex=ZERO.hex()), dict(member=SD_NAME, offset=40916, before_hex=PROFILE['sd_version_gate']['original_hex'], after_hex=ONE.hex())]
    patches += [dict(member=CC_NAME, offset=s['offset'], before_hex=s['original_hex'], after_hex=s['patched_hex']) for s in PROFILE['chkfirm_version_gate']['sites']]
    return dict(schema='m4-current-receiver-semantics/2', patch_set=PATCH_SET, before=before, after=after, bytes=P1_BYTES, source_sha256=sha(old), candidate_sha256=sha(new), spans=spans, windows=windows, changed_bytes=sum((a != b for a, b in zip(old, new))), window_count=len(windows), stage_bytes=sum((2 * r['length'] for r in windows)), outside_spans_unchanged=True, partition_tail_unchanged=True, only_library_bytes_changed=patches, all_other_contents_metadata_links_unchanged=True, public_key_unchanged=True, verifyKey_unchanged=True, device_files_unchanged=True, signature_gate_added=True, core_gates_added=True, hardware_operations=0)

def prepare(source, expected_sha256, output):
    pins = source_pins()
    require(expected_sha256.lower() == SOURCE_P1_SHA, 'Preparation requires the explicit current source SHA')
    path = locked(source, expected_sha256)
    raw = path.read_bytes()
    before, fat, initrd, _, contents, _ = inspect_bytes(raw)
    require(before['trust_state'] in SOURCE_STATES, 'Not the current user-key baseline')
    replacements = expected_libraries(contents)
    output = new_dir(output)
    work = new_dir(output / 'work')
    rebuilt = helper.rebuild_initrd(initrd, replacements, work)
    result = bytearray(raw)

    def put(stream, offset, value):
        for disk, start, count in helper.map_range(fat, stream, offset, len(value)):
            require(0 <= disk < disk + count <= FAT_BYTES, 'Change outside existing FAT image')
            result[disk:disk + count] = value[start:start + count]
    stream = fat.get('boot/initrd.img').open()
    allocated = sum((n * stream.block_size for _, n in stream._runlist))
    require(len(rebuilt) <= allocated, 'New initrd exceeds existing allocation; relocation forbidden')
    put(stream, 0, rebuilt + bytes(allocated - len(rebuilt)))
    boot = fat.get('boot').open()
    directory = boot.read()
    hits = [i for i in range(0, len(directory) - 31, 32) if directory[i:i + 11] == b'INITRD  IMG']
    require(len(hits) == 1, 'Ambiguous initrd directory entry')
    sizeoff = hits[0] + 28
    require(struct.unpack_from('<I', directory, sizeoff)[0] == len(initrd), 'Original initrd size differs')
    put(boot, sizeoff, struct.pack('<I', len(rebuilt)))
    sums = fat.get('p1chksum').open()
    original = sums.read()
    replacement = original.replace(hashlib.md5(initrd).hexdigest().encode(), hashlib.md5(rebuilt).hexdigest().encode())
    require(len(replacement) == len(original) and replacement != original, 'p1chksum update failed')
    put(sums, 0, replacement)
    candidate = bytes(result)
    semantics = verify_patch_semantics(raw, candidate)
    require(file_sha(path) == SOURCE_P1_SHA and source_pins() == pins, 'Input or semantic dependencies changed')
    (output / 'p1_original.bin').write_bytes(raw)
    (output / 'p1_candidate.bin').write_bytes(candidate)
    manifest = {**semantics, 'schema': SCHEMA, 'original': 'p1_original.bin', 'candidate': 'p1_candidate.bin', 'source': str(path), 'key_sha256': KEY_SHA, 'adapter_sources': pins, 'status': 'OFFLINE_CURRENT_SOURCE_BUNDLE_NOT_HARDWARE_WRITTEN', 'current_body_verified': False, 'restore_role': RESTORE_ROLE, 'no_packaged_image_transplant': True, 'no_partition_allocation_change': True}
    save_json(output / 'bundle.json', manifest)
    return manifest

def load_bundle(directory):
    directory = local_path(directory)
    manifest = json.loads(local_path(directory / 'bundle.json', existing=True).read_text('utf-8-sig'))
    require(manifest['schema'] == SCHEMA and manifest['patch_set'] == PATCH_SET and (manifest['original'] == 'p1_original.bin') and (manifest['candidate'] == 'p1_candidate.bin') and (manifest['bytes'] == P1_BYTES) and (manifest['adapter_sources'] == source_pins()) and (manifest['source_sha256'] == SOURCE_P1_SHA) and (manifest['restore_role'] == RESTORE_ROLE), 'Wrong/unbound current-source bundle')
    old = locked(directory / 'p1_original.bin', manifest['source_sha256']).read_bytes()
    new = locked(directory / 'p1_candidate.bin', manifest['candidate_sha256']).read_bytes()
    check = verify_patch_semantics(old, new)
    for key, value in check.items():
        if key != 'schema':
            require(manifest.get(key) == value, 'Bundle semantic evidence differs: ' + key)
    require(manifest['key_sha256'] == KEY_SHA, 'Wrong bundle public key')
    return (manifest, old, new)

def replay(bundle, current, expected, direction, output):
    manifest, old, new = load_bundle(bundle)
    require(direction in ('apply', 'restore'), 'Unsupported replay direction')
    path = locked(current, expected)
    actual = path.read_bytes()
    state = inspect_bytes(actual)[0]
    before, after = (old, new) if direction == 'apply' else (new, old)
    already = direction == 'restore' and all((actual[r['offset']:r['offset'] + r['length']] == old[r['offset']:r['offset'] + r['length']] for r in manifest['spans']))
    if direction == 'apply':
        require(sha(actual) == SOURCE_P1_SHA and state['trust_state'] in SOURCE_STATES, 'Apply needs exact current original')
    else:
        require(state['trust_state'] == (manifest['before']['trust_state'] if already else GOOD_STATE), 'Restore source has unknown or mixed state')
    for row in manifest['spans']:
        a, n = (row['offset'], row['length'])
        require(already or actual[a:a + n] == before[a:a + n], 'Saved window changed; do not restore blindly')
    result = bytearray(actual)
    if not already:
        for row in manifest['spans']:
            a, n = (row['offset'], row['length'])
            result[a:a + n] = after[a:a + n]
    result = bytes(result)
    after_state = inspect_bytes(result)[0]
    require(after_state['trust_state'] == (GOOD_STATE if direction == 'apply' else manifest['before']['trust_state']), 'Replay target state differs')
    cursor = 0
    for row in manifest['spans']:
        a, n = (row['offset'], row['length'])
        require(actual[cursor:a] == result[cursor:a], 'Replay changed outside saved windows')
        cursor = a + n
    require(actual[cursor:] == result[cursor:] and file_sha(path) == expected.lower(), 'Replay tail/source changed')
    output = new_dir(output)
    (output / ('p1_' + direction + '.bin')).write_bytes(result)
    receipt = dict(schema='m4-current-receiver-replay/2', patch_set=PATCH_SET, direction=direction, input_sha256=sha(actual), output_sha256=sha(result), bytes=P1_BYTES, checked_windows=len(manifest['spans']), outside_windows_preserved=True, exact_original_restored=result == old, already_restored=already, before_state=state['trust_state'], after_state=after_state['trust_state'], target_version_return_value=after_state['version_boolean_return'], restore_role=RESTORE_ROLE if direction == 'restore' else None, status='LOCAL_FILE_REPLAY_ONLY', current_body_verified=False, camera_io=False, hardware_operations=0)
    save_json(output / 'receipt.json', receipt)
    return receipt
