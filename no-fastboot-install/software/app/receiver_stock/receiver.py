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
from byte_diff import count_differences
CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
LOW_PATH = CASE.parent / 'receiver_shared/receiver_adapter.py'
LOW_SHA = pinned('app/receiver_shared/receiver_adapter.py')
if hashlib.sha256(LOW_PATH.read_bytes()).hexdigest() != LOW_SHA:
    raise ValueError('Frozen container helper changed')
spec = importlib.util.spec_from_file_location('_m4_reusable_receiver_container', LOW_PATH)
low = importlib.util.module_from_spec(spec)
spec.loader.exec_module(low)
helper, PROFILE = (low.helper, low.PROFILE)
require, sha, file_sha = (low.require, low.sha, low.file_sha)
locked, local_path, new_dir, save_json = (low.locked, low.local_path, low.new_dir, low.save_json)
P1_BYTES, FAT_BYTES, MAX_WINDOW = (low.P1_BYTES, low.FAT_BYTES, low.MAX_WINDOW)
SD_NAME, CC_NAME, KEY_SHA = (low.SD_NAME, low.CC_NAME, PROFILE['stock_public_key_sha256'])
ZERO, ONE = (low.ZERO, low.ONE)
SCHEMA = 'm4-reviewed-full-p1-bundle/1'
PATCH_SET = 'sd-signature-success0-version-true1-core/1'
GOOD_STATE = 'stock_key_version_true'
SOURCE_STATES = ('stock_key_gate', GOOD_STATE)
SD_SOURCE_SHA = PROFILE['libraries']['libsdfileinputupdaterapi.so']['original_sha256']
SD_GOOD_SHA = 'f6c68faca339cadff1c1bda5aca9971fb4fcf3af5ac5150ccb6e59f489b65c75'
CC_SOURCE_SHA = PROFILE['chkfirm_version_gate']['original_sha256']
CC_GOOD_SHA = PROFILE['chkfirm_version_gate']['patched_sha256']
STATES = {SD_SOURCE_SHA: ('stock_key_gate', False, None, CC_SOURCE_SHA), SD_GOOD_SHA: (GOOD_STATE, True, 1, CC_GOOD_SHA)}

def source_pins():
    require(file_sha(LOW_PATH) == LOW_SHA, 'Frozen container helper changed')
    return {**low.source_pins(), **{(CASE / name).relative_to(ROOT).as_posix(): file_sha(CASE / name) for name in ('receiver.py', 'byte_diff.py')}}

def library_state(data, entry):
    """Exact ELF hashes plus symbol, instruction, caller and vtable checks."""
    digest = sha(data)
    is_sd = entry == PROFILE['libraries']['libsdfileinputupdaterapi.so']
    require(digest in (STATES if is_sd else {entry['original_sha256']}), 'Unknown updater library')
    elf = low.ELFFile(io.BytesIO(data))
    require(elf.elfclass == 64 and elf.little_endian and (elf['e_machine'] == 'EM_AARCH64'), 'Reviewed M4 AArch64 ELF required')
    offset = low.symbol_offset(elf, low.VERIFY_KEY, entry['va'])
    require(offset == entry['offset'] and data[offset:offset + 8] == bytes.fromhex(entry['original_hex']), 'Existing verifyKey entry changed')
    report = dict(sha256=digest, bytes=len(data), symbol=low.VERIFY_KEY, va=entry['va'], file_offset=offset, entry_hex=bytes.fromhex(entry['original_hex']).hex(), patched=False, signature_bypass=False)
    if is_sd:
        _, signature, version, _ = STATES[digest]
        sig, ver = (PROFILE['sd_signature_gate'], PROFILE['sd_version_gate'])
        sigoff = low.symbol_offset(elf, sig['symbol'], sig['va'], sig['size'])
        veroff = low.symbol_offset(elf, ver['symbol'], ver['va'], ver['size'])
        require(sigoff == 44016 and veroff == 40916, 'SD gate mapping differs')
        expected_version = bytes.fromhex(ver['original_hex']) if version is None else ONE if version == 1 else ZERO
        require(data[sigoff:sigoff + 8] == (ZERO if signature else bytes.fromhex(sig['original_hex'])), 'Signature entry differs from reviewed state')
        require(data[veroff:veroff + 8] == expected_version, 'Version predicate entry differs')
        caller = sig['caller']
        require(data[caller['va']:caller['va'] + 4].hex() == caller['call_hex'] and data[caller['result_va']:caller['result_va'] + 4].hex() == caller['result_hex'], 'Signature status consumer differs')
        call = bytes.fromhex(ver['caller_hex'])
        require(data[ver['caller_va']:ver['caller_va'] + len(call)] == call, 'Version Boolean consumer differs')
        low.check_vtable(elf)
        report.update(signature_bypass=signature, version_bypass=version is not None, signature_function=dict(va=sigoff, return_value=0 if signature else None), version_function=dict(va=veroff, return_value=version), boolean_caller_verified=True, version_vtable_verified=True)
    return report
helper.library_state = library_state

def inspect_bytes(raw):
    require(isinstance(raw, (bytes, bytearray)) and len(raw) == P1_BYTES, 'A full 25100288-byte p1 is required; packaged FAT volumes are forbidden')
    report, fat, initrd, inventory, contents, links = helper.inspect_bytes(raw)
    require(report['fat_bytes'] == FAT_BYTES and fat.sector_size * fat.total_sectors == FAT_BYTES, 'Reviewed FAT geometry required')
    require(report['key_sha256'] == KEY_SHA and all((not r['patched'] for r in report['libraries'].values())), 'Expected official public key and original verifyKey entries')
    sd = report['libraries']['libsdfileinputupdaterapi.so']
    state, signature, version, cc_sha = STATES[sd['sha256']]
    require(sha(contents[CC_NAME]) == cc_sha, 'Mixed SD/core gate state')
    sd['version_gate_modified'] = sd.pop('version_bypass')
    sd['version_condition_forced_true'] = version == 1
    report.update(schema='m4-reviewed-full-p1-state/1', state=state, trust_state=state, signature_success_status=0, signature_gate_forced_success=signature, version_boolean_return=version, version_predicate_mode='original_version_comparison' if version is None else 'forced_true' if version == 1 else 'forced_false', known_bad_version_boolean=version == 0, current_body_verified=False, partition_tail_sha256=sha(raw[FAT_BYTES:]), partition_tail_bytes=P1_BYTES - FAT_BYTES, device_file_sha256={n: report['files'][n] for n in ('dat1', 'dat2', 'dat3', 'dat4') if n in report['files']}, live_writer_enabled=False, camera_io=False)
    return (report, fat, initrd, inventory, contents, links)

def inspect(path, expected_sha256):
    path = locked(path, expected_sha256)
    value = inspect_bytes(path.read_bytes())[0]
    require(file_sha(path) == expected_sha256.lower(), 'Source changed during inspection')
    return value

def expected_libraries(contents):
    sd = bytearray(contents[SD_NAME])
    require(sha(sd) in STATES, 'Unknown SD source')
    sd[44016:44024] = ZERO
    sd[40916:40924] = ONE
    require(sha(sd) == SD_GOOD_SHA, 'Unexpected change outside SD gates')
    cc = bytearray(contents[CC_NAME])
    require(sha(cc) in (CC_SOURCE_SHA, CC_GOOD_SHA), 'Unknown core source')
    for row in PROFILE['chkfirm_version_gate']['sites']:
        off, size = (row['offset'], row['length'])
        require(cc[off:off + size].hex() in (row['original_hex'], row['patched_hex']), 'Unknown core entry')
        cc[off:off + size] = bytes.fromhex(row['patched_hex'])
    require(sha(cc) == CC_GOOD_SHA, 'Unexpected change outside core gates')
    return {SD_NAME: bytes(sd), CC_NAME: bytes(cc)}

def verify_patch_semantics(old, new):
    before, fat, _, inventory, contents, links = inspect_bytes(old)
    after, _, _, new_inventory, new_contents, new_links = inspect_bytes(new)
    require(after['state'] == GOOD_STATE, 'Candidate does not return version Boolean true')
    replacements = expected_libraries(contents)
    require(new_contents == {**contents, **replacements}, 'Unlisted initrd content change')
    expected_inventory = copy.deepcopy(inventory)
    for name, value in replacements.items():
        expected_inventory[name].update(bytes=len(value), sha256=sha(value))
    require(new_inventory == expected_inventory and new_links == links, 'SquashFS metadata or links changed')
    require(contents['etc/VerificationKey.pem'] == new_contents['etc/VerificationKey.pem'], 'Public key changed')
    keep = lambda r: {n: h for n, h in r['files'].items() if n not in ('boot/initrd.img', 'p1chksum')}
    require(keep(before) == keep(after), 'Device data or other FAT files changed')
    spans, cursor = ([], 0)
    for start, length, purpose in low.allowed_regions(fat):
        require(old[cursor:start] == new[cursor:start], 'Change outside existing FAT allocation')
        spans.append(dict(offset=start, length=length, purpose=purpose, before_sha256=sha(old[start:start + length]), after_sha256=sha(new[start:start + length])))
        cursor = start + length
    require(old[cursor:] == new[cursor:] and old[FAT_BYTES:] == new[FAT_BYTES:], 'Unlisted FAT bytes or physical partition tail changed')
    windows = low.windowdiff(old, new, spans) if old != new else []
    patches = []
    for name in (SD_NAME, CC_NAME):
        locations = ((44016, 8), (40916, 8)) if name == SD_NAME else tuple(((r['offset'], r['length']) for r in PROFILE['chkfirm_version_gate']['sites']))
        for off, size in locations:
            a, b = (contents[name][off:off + size], new_contents[name][off:off + size])
            if a != b:
                patches.append(dict(member=name, offset=off, before_hex=a.hex(), after_hex=b.hex()))
    require(old != new or before['state'] == GOOD_STATE, 'Unexpected empty adaptation')
    return dict(schema='m4-reviewed-full-p1-semantics/1', patch_set=PATCH_SET, before=before, after=after, bytes=P1_BYTES, source_sha256=sha(old), candidate_sha256=sha(new), spans=spans, windows=windows, changed_bytes=count_differences(old, new), window_count=len(windows), stage_bytes=sum((2 * r['length'] for r in windows)), outside_spans_unchanged=True, partition_tail_unchanged=True, only_library_bytes_changed=patches, all_other_contents_metadata_links_unchanged=True, public_key_unchanged=True, verifyKey_unchanged=True, device_files_unchanged=True, already_adapted=old == new, live_writer_enabled=False, hardware_operations=0)

def prepare(source, expected_sha256, output):
    pins = source_pins()
    path = locked(source, expected_sha256)
    raw = path.read_bytes()
    before, fat, initrd, _, contents, _ = inspect_bytes(raw)
    replacements = expected_libraries(contents)
    out = new_dir(output)
    result = bytearray(raw)
    if before['state'] != GOOD_STATE:
        work = new_dir(out / 'work')
        rebuilt = helper.rebuild_initrd(initrd, replacements, work)

        def put(stream, offset, value):
            for disk, start, count in helper.map_range(fat, stream, offset, len(value)):
                require(0 <= disk < disk + count <= FAT_BYTES, 'Write outside existing FAT image')
                result[disk:disk + count] = value[start:start + count]
        stream = fat.get('boot/initrd.img').open()
        allocated = sum((n * stream.block_size for _, n in stream._runlist))
        require(len(rebuilt) <= allocated, 'Initrd exceeds existing allocation; relocation forbidden')
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
    require(file_sha(path) == expected_sha256.lower() and source_pins() == pins, 'Input or source dependency changed')
    (out / 'p1_original.bin').write_bytes(raw)
    (out / 'p1_candidate.bin').write_bytes(candidate)
    manifest = {**semantics, 'schema': SCHEMA, 'source': str(path), 'original': 'p1_original.bin', 'candidate': 'p1_candidate.bin', 'recovery': 'p1_original.bin', 'key_sha256': KEY_SHA, 'adapter_sources': pins, 'status': 'NO_CHANGE_NEEDED' if raw == candidate else 'OFFLINE_BUNDLE_NOT_HARDWARE_WRITTEN', 'restore_role': 'rollback_to_this_saved_full_source', 'current_body_verified': False, 'no_packaged_image_transplant': True, 'no_partition_allocation_change': True}
    save_json(out / 'bundle.json', manifest)
    return manifest

def load_bundle(directory):
    directory = local_path(directory)
    m = json.loads(local_path(directory / 'bundle.json', existing=True).read_text('utf-8-sig'))
    require(m['schema'] == SCHEMA and m['patch_set'] == PATCH_SET and (m['original'] == m['recovery'] == 'p1_original.bin') and (m['candidate'] == 'p1_candidate.bin') and (m['bytes'] == P1_BYTES) and (m['key_sha256'] == KEY_SHA) and (m['adapter_sources'] == source_pins()) and (m['restore_role'] == 'rollback_to_this_saved_full_source'), 'Unbound or unsupported bundle')
    old = locked(directory / 'p1_original.bin', m['source_sha256']).read_bytes()
    new = locked(directory / 'p1_candidate.bin', m['candidate_sha256']).read_bytes()
    check = verify_patch_semantics(old, new)
    for key, value in check.items():
        if key != 'schema':
            require(m.get(key) == value, 'Bundle semantic evidence differs: ' + key)
    require(m['status'] == ('NO_CHANGE_NEEDED' if old == new else 'OFFLINE_BUNDLE_NOT_HARDWARE_WRITTEN'), 'Bundle no-change status differs')
    return (m, old, new)

def replay(bundle, current, expected, direction, output):
    require(direction in ('apply', 'restore'), 'Unsupported replay direction')
    m, old, new = load_bundle(bundle)
    path = locked(current, expected)
    actual = path.read_bytes()
    before_report = inspect_bytes(actual)[0]
    before, after = (old, new) if direction == 'apply' else (new, old)
    if direction == 'apply':
        require(sha(actual) == m['source_sha256'], 'Apply needs the exact captured source')
    already = direction == 'restore' and all((actual[r['offset']:r['offset'] + r['length']] == old[r['offset']:r['offset'] + r['length']] for r in m['spans']))
    require(before_report['state'] == (m['before']['state'] if direction == 'apply' or already else GOOD_STATE), 'Replay source has an unexpected state')
    result = bytearray(actual)
    for row in m['spans']:
        a, n = (row['offset'], row['length'])
        require(already or actual[a:a + n] == before[a:a + n], 'Saved region differs; do not restore blindly')
        if not already:
            result[a:a + n] = after[a:a + n]
    result = bytes(result)
    target = inspect_bytes(result)[0]
    require(target['state'] == (GOOD_STATE if direction == 'apply' else m['before']['state']), 'Wrong target state')
    cursor = 0
    for row in m['spans']:
        a, n = (row['offset'], row['length'])
        require(actual[cursor:a] == result[cursor:a], 'Replay changed outside saved regions')
        cursor = a + n
    require(actual[cursor:] == result[cursor:] and file_sha(path) == expected.lower(), 'Replay tail or input changed')
    out = new_dir(output)
    name = 'p1_' + direction + '.bin'
    (out / name).write_bytes(result)
    receipt = dict(schema='m4-reviewed-full-p1-replay/1', direction=direction, input_sha256=sha(actual), output_sha256=sha(result), output=name, bytes=P1_BYTES, checked_windows=len(m['spans']), before_state=before_report['state'], after_state=target['state'], already_restored=already, exact_original_restored=result == old, outside_windows_preserved=True, hardware_operations=0, camera_io=False, live_writer_enabled=False, current_body_verified=False, status='LOCAL_FILE_REPLAY_ONLY')
    save_json(out / 'receipt.json', receipt)
    return receipt
