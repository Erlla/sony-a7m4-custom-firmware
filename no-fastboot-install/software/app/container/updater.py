from __future__ import annotations
from product_integrity import pinned, state_path
import copy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import struct
import subprocess
import tarfile
from common import ROOT, dependencies, file_sha, local_path, locked, new_dir, require, save_json, sha
dependencies()
from dissect.fat import FATFS
from dissect.squashfs import SquashFS
from elftools.elf.elffile import ELFFile
PROFILE = json.loads((Path(__file__).parent / 'm4_profile.json').read_text('utf-8'))
STUB = bytes.fromhex('00008052c0035fd6')
SYMBOL = '_ZN7Updater21SignatureVerification9verifyKeyEPKc'
SD_GATE = PROFILE['sd_signature_gate']
SD_VER_GATE = PROFILE['sd_version_gate']
CHK_GATE = PROFILE['chkfirm_version_gate']
SD_LIB_NAME = 'usr/lib/' + SD_GATE['library']
CC_LIB_NAME = 'usr/lib/' + CHK_GATE['library']

def _gate_offsets(elf, symbol, va, size):
    """One defined dynsym, mapped in one executable PT_LOAD; file offset returned."""
    hits = [s for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name == symbol and s['st_shndx'] != 'SHN_UNDEF']
    require(len(hits) == 1, 'Expected one defined symbol: ' + symbol)
    s = hits[0]
    require(s['st_value'] == va and s['st_size'] == size, 'Gate symbol mapping changed: ' + symbol)
    segs = [t for t in elf.iter_segments() if t['p_type'] == 'PT_LOAD' and t['p_vaddr'] <= s['st_value'] and (s['st_value'] + size <= t['p_vaddr'] + t['p_filesz'])]
    require(len(segs) == 1 and segs[0]['p_flags'] & 1, 'Gate not in one executable segment: ' + symbol)
    return segs[0]['p_offset'] + s['st_value'] - segs[0]['p_vaddr']

def library_state(data, profile):
    digest = sha(data)
    gate = SD_GATE
    ver = SD_VER_GATE
    is_sd = profile == PROFILE['libraries'][gate['library']]
    sd_digests = {profile['original_sha256']: (False, False), profile['patched_sha256']: (False, False), gate['patched_sha256']: (True, False), gate['patched_on_existing_selfsign_sha256']: (True, False), ver['patched_sha256']: (True, True), ver['patched_on_existing_selfsign_sha256']: (True, True)}
    known = digest in (profile['original_sha256'], profile['patched_sha256'])
    signature_bypass = False
    version_bypass = False
    if is_sd:
        require(digest in sd_digests, 'Unreviewed updater library')
        signature_bypass, version_bypass = sd_digests[digest]
    else:
        require(known, 'Unreviewed updater library')
    e = ELFFile(io.BytesIO(data))
    require(e.elfclass == 64 and e.little_endian and (e['e_machine'] == 'EM_AARCH64'), 'M4 AArch64 ELF required')
    symbols = [s for s in e.get_section_by_name('.dynsym').iter_symbols() if s.name == SYMBOL and s['st_shndx'] != 'SHN_UNDEF']
    require(len(symbols) == 1, 'verifyKey must have one defined symbol')
    s = symbols[0]
    segments = [t for t in e.iter_segments() if t['p_type'] == 'PT_LOAD' and t['p_vaddr'] <= s['st_value'] and (s['st_value'] + 8 <= t['p_vaddr'] + t['p_filesz'])]
    require(len(segments) == 1 and segments[0]['p_flags'] & 1, 'verifyKey is not in one executable file segment')
    t = segments[0]
    offset = t['p_offset'] + s['st_value'] - t['p_vaddr']
    patched = digest == profile['patched_sha256'] or (is_sd and digest in (gate['patched_on_existing_selfsign_sha256'], ver['patched_on_existing_selfsign_sha256']))
    require(offset == profile['offset'] and s['st_value'] == profile['va'], 'M4 symbol mapping changed')
    expected = STUB if patched else bytes.fromhex(profile['original_hex'])
    require(data[offset:offset + 8] == expected, 'verifyKey entry differs')
    result = dict(sha256=digest, bytes=len(data), symbol=SYMBOL, va=s['st_value'], file_offset=offset, entry_hex=expected.hex(), patched=patched, signature_bypass=signature_bypass)
    if is_sd:
        result['version_bypass'] = version_bypass
        sigoff = _gate_offsets(e, gate['symbol'], gate['va'], gate['size'])
        require(sigoff == gate['offset'], 'SD signature gate mapping differs')
        require(data[sigoff:sigoff + 8] == (STUB if signature_bypass else bytes.fromhex(gate['original_hex'])), 'SD signature gate entry differs')
        caller = gate['caller']
        require(data[caller['va']:caller['va'] + 4].hex() == caller['call_hex'] and data[caller['result_va']:caller['result_va'] + 4].hex() == caller['result_hex'], 'SD signature caller differs')
        veroff = _gate_offsets(e, ver['symbol'], ver['va'], ver['size'])
        require(veroff == ver['offset'], 'SD version gate mapping differs')
        require(data[veroff:veroff + 8] == (STUB if version_bypass else bytes.fromhex(ver['original_hex'])), 'SD version gate entry differs')
        result['signature_function'] = dict(symbol=gate['symbol'], va=gate['va'], file_offset=sigoff, bypass=signature_bypass, return_value=0 if signature_bypass else None)
        result['version_function'] = dict(symbol=ver['symbol'], va=ver['va'], file_offset=veroff, bypass=version_bypass, return_value=0 if version_bypass else None)
    return result

def chkfirm_state(data):
    """State of the p1 base-environment downgrade gate library."""
    gate = CHK_GATE
    digest = sha(data)
    patched = digest == gate['patched_sha256']
    require(digest in (gate['original_sha256'], gate['patched_sha256']), 'Unreviewed chkFirmInfo library')
    e = ELFFile(io.BytesIO(data))
    require(e.elfclass == 64 and e.little_endian and (e['e_machine'] == 'EM_AARCH64'), 'M4 AArch64 ELF required')
    base = _gate_offsets(e, gate['symbol'], gate['va'], gate['size'])
    sites = []
    for site in gate['sites']:
        offset = base + (site['va'] - gate['va'])
        require(offset == site['offset'], 'chkFirmInfo site mapping differs')
        expected = bytes.fromhex(site['patched_hex'] if patched else site['original_hex'])
        require(data[offset:offset + site['length']] == expected, 'chkFirmInfo gate site differs')
        sites.append(dict(va=site['va'], file_offset=offset, hex=expected.hex(), patched=patched, semantics=site['semantics']))
    return dict(sha256=digest, bytes=len(data), symbol=gate['symbol'], va=gate['va'], file_offset=base, patched=patched, version_bypass=patched, sites=sites)

def squash_inventory(raw):
    fs = SquashFS(io.BytesIO(raw))
    require(fs.sb.xattr_id_table_start in (-1, 18446744073709551615), 'Unreviewed xattrs cannot be discarded')
    result, contents, groups = ({}, {}, {})

    def visit(node, name):
        row = dict(mode=node.mode, uid=node.uid, gid=node.gid, mtime=int(node.mtime.timestamp()))
        if node.is_dir():
            row['kind'] = 'dir'
        elif node.is_file():
            data = node.open().read()
            contents[name] = data
            row.update(kind='file', bytes=len(data), sha256=sha(data))
            groups.setdefault(node.inode_number, []).append(name)
        elif node.is_symlink():
            row.update(kind='symlink', link=node.link)
        elif node.is_device():
            row.update(kind='device', rdev=node.header.rdev)
        elif node.is_ipc():
            row['kind'] = 'ipc'
        else:
            raise ValueError('Unreviewed special inode')
        require(name not in result, 'Duplicate SquashFS path')
        result[name] = row
        if node.is_dir():
            for child in node.iterdir():
                require(child.name not in ('.', '..') and '/' not in child.name, 'Invalid SquashFS name')
                visit(child, (name + '/' + child.name).lstrip('/'))
    visit(fs.root, '')
    return (result, contents, sorted((sorted(v) for v in groups.values() if len(v) > 1)))

def inspect_bytes(raw):
    require(len(raw) in PROFILE['p1_sizes'], 'Unsupported M4 p1 length')
    f = FATFS(io.BytesIO(raw))
    require(f.sector_size * f.total_sectors == PROFILE['fat_bytes'], 'Unsupported M4 FAT geometry')
    initrd = f.get('boot/initrd.img').open().read()
    kernel = f.get('boot/vmlinux.bin').open().read()
    checksum = (hashlib.md5(kernel).hexdigest() + '  ./boot/vmlinux.bin\n' + hashlib.md5(initrd).hexdigest() + '  ./boot/initrd.img\n').encode('ascii')
    require(f.get('p1chksum').open().read() == checksum, 'p1chksum mismatch')
    inv, data, links = squash_inventory(initrd)
    key = data['etc/VerificationKey.pem']
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    k = serialization.load_pem_public_key(key)
    require(isinstance(k, rsa.RSAPublicKey) and k.key_size == 2048, 'p1 key is not RSA-2048')
    libs = {name: library_state(data['usr/lib/' + name], p) for name, p in PROFILE['libraries'].items()}
    states = {v['patched'] for v in libs.values()}
    require(len(states) == 1, 'Mixed stock and modified trust gates')
    modified = states == {True}
    sd_lib = libs[SD_GATE['library']]
    bypass = sd_lib['signature_bypass']
    version_bypass_sd = sd_lib.get('version_bypass', False)
    chkfirm = chkfirm_state(data[CC_LIB_NAME])
    version_bypass_cc = chkfirm['version_bypass']
    if version_bypass_sd or version_bypass_cc:
        require(bypass and version_bypass_sd and version_bypass_cc, 'Partial version gate state is unreviewed')
    if not modified:
        require(sha(key) == PROFILE['stock_public_key_sha256'], 'Stock gates with an unreviewed public key')
    files = {}

    def walk(node, prefix=''):
        for child in node.iterdir():
            if child.name in ('.', '..'):
                continue
            name = prefix + child.name
            if child.is_directory():
                walk(child, name + '/')
            else:
                require(name not in files, 'Duplicate FAT path')
                files[name] = sha(child.open().read())
    walk(f.get('/'))
    if 'dat2' in files:
        require(f.get('dat2').open().read() == struct.pack('<I', 16973953), 'Wrong p1 model')
    report = dict(model='01030081', bytes=len(raw), sha256=sha(raw), fat_bytes=PROFILE['fat_bytes'], role='packaged_volume' if len(raw) == PROFILE['fat_bytes'] else 'full_partition_file', initrd_sha256=sha(initrd), initrd_bytes=len(initrd), p1chksum_valid=True, key_sha256=sha(key), key_sha1=hashlib.sha1(key).hexdigest(), trust_state='downgrade_bypass' if bypass and version_bypass_sd and version_bypass_cc else 'sd_signature_bypass' if bypass else 'user_key_gate' if modified else 'stock_key_gate', baseline_key_state='existing_user_key' if modified else 'official_key', libraries=libs, chkfirm_version_gate=chkfirm, files=files, squashfs_entries=len(inv), current_body_verified=False, camera_io=False)
    return (report, f, initrd, inv, data, links)

def inspect(path, expected):
    path = locked(path, expected)
    return inspect_bytes(path.read_bytes())[0]

def map_range(fs, stream, offset, length):
    base = fs.first_data_sector * fs.sector_size
    block = stream.block_size
    logical = total = 0
    result = []
    for disk, count in stream._runlist:
        require(disk is not None, 'Sparse FAT run')
        a, b = (max(offset, logical), min(offset + length, logical + count * block))
        if b > a:
            result.append((base + disk * block + a - logical, a - offset, b - a))
            total += b - a
        logical += count * block
    require(total == length, 'FAT range exceeds allocation')
    return result

def rebuild_initrd(initrd, replacements, work):
    tools = ROOT / PROFILE['squash_tools_directory']
    for name, digest in PROFILE['squash_tools'].items():
        locked(tools / name, digest)
    (work / 'source.img').write_bytes(initrd)
    with (work / 'source.tar').open('xb') as out:
        subprocess.run([str(tools / 'sqfs2tar.exe'), '--no-skip', '--root-becomes', '.', 'source.img'], cwd=work, stdout=out, stderr=subprocess.PIPE, check=True, timeout=120)
    changed = set()
    with tarfile.open(work / 'source.tar', 'r:') as src, tarfile.open(work / 'modified.tar', 'x', format=tarfile.PAX_FORMAT) as dst:
        for m in src:
            name = m.name.removeprefix('./').rstrip('/')
            require(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts, 'Unsafe tar path')
            member = copy.copy(m)
            if name in replacements:
                require(name not in changed and m.isfile(), 'Patch target must be one regular file')
                value = replacements[name]
                member.size = len(value)
                dst.addfile(member, io.BytesIO(value))
                changed.add(name)
            else:
                dst.addfile(member, src.extractfile(m) if m.isfile() else None)
    require(changed == replacements.keys(), 'Missing initrd patch target')
    with (work / 'modified.tar').open('rb') as source:
        subprocess.run([str(tools / 'tar2sqfs.exe'), '--no-skip', '--quiet', '-j', '1', '-c', 'gzip', '-b', '131072', '--exportable', 'candidate.img'], cwd=work, stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=120)
    return (work / 'candidate.img').read_bytes()

def prepare(path, expected, output):
    source = locked(path, expected)
    raw = source.read_bytes()
    before, fs, initrd, inv, data, links = inspect_bytes(raw)
    require(before['trust_state'] in ('stock_key_gate', 'user_key_gate', 'sd_signature_bypass', 'downgrade_bypass'), 'Unreviewed baseline')
    out = new_dir(output)
    work = out / 'work'
    work.mkdir()
    gate = SD_GATE
    ver = SD_VER_GATE
    sd_name = 'usr/lib/' + gate['library']
    lib = bytearray(data[sd_name])
    lib[gate['offset']:gate['offset'] + 8] = STUB
    lib[ver['offset']:ver['offset'] + 8] = bytes.fromhex(ver['stub_hex'])
    expected_patch = ver['patched_on_existing_selfsign_sha256'] if before['libraries'][gate['library']]['patched'] else ver['patched_sha256']
    require(sha(lib) == expected_patch, 'Unexpected change outside the reviewed SD gates')
    cc = bytearray(data[CC_LIB_NAME])
    cc_sites = []
    for site in CHK_GATE['sites']:
        cc[site['offset']:site['offset'] + site['length']] = bytes.fromhex(site['patched_hex'])
        cc_sites.append(site['va'])
    require(sha(cc) == CHK_GATE['patched_sha256'], 'Unexpected change outside chkFirmInfo gates')
    replacements = {sd_name: bytes(lib), CC_LIB_NAME: bytes(cc)}
    if all((data[name] == value for name, value in replacements.items())):
        new_initrd = initrd
    else:
        new_initrd = rebuild_initrd(initrd, replacements, work)
    new_inv, new_data, new_links = squash_inventory(new_initrd)
    expected_inv = copy.deepcopy(inv)
    for name, value in replacements.items():
        expected_inv[name].update(bytes=len(value), sha256=sha(value))
    require(new_inv == expected_inv and links == new_links, 'Unexpected filesystem content/metadata/link changes')
    require(new_data == {**data, **replacements}, 'Unexpected initrd file changes')
    result, spans = (bytearray(raw), [])

    def put(stream, offset, value, purpose):
        for disk, start, count in map_range(fs, stream, offset, len(value)):
            require(0 <= disk < disk + count <= len(result), 'FAT write outside source')
            result[disk:disk + count] = value[start:start + count]
            spans.append(dict(offset=disk, length=count, purpose=purpose))
    if new_initrd != initrd:
        stream = fs.get('boot/initrd.img').open()
        allocated = sum((count * stream.block_size for disk, count in stream._runlist))
        require(len(new_initrd) <= allocated, 'Rebuilt initrd exceeds existing FAT chain; allocation forbidden')
        put(stream, 0, new_initrd + bytes(allocated - len(new_initrd)), 'initrd existing allocation')
        boot = fs.get('boot').open()
        directory = boot.read()
        entries = [i for i in range(0, len(directory) - 31, 32) if directory[i:i + 11] == b'INITRD  IMG']
        require(len(entries) == 1, 'Ambiguous initrd directory entry')
        off = entries[0] + 28
        require(struct.unpack_from('<I', directory, off)[0] == len(initrd), 'Old directory length differs')
        put(boot, off, struct.pack('<I', len(new_initrd)), 'initrd file size')
        sums = fs.get('p1chksum').open()
        old = sums.read()
        new = old.replace(hashlib.md5(initrd).hexdigest().encode(), hashlib.md5(new_initrd).hexdigest().encode())
        require(len(new) == len(old) and new != old, 'p1chksum replacement failed')
        put(sums, 0, new, 'p1chksum')
    after = inspect_bytes(bytes(result))[0]
    require(after['trust_state'] == 'downgrade_bypass' and after['key_sha256'] == before['key_sha256'], 'Signature and version gate adaptation failed')
    require({k: v for k, v in before['files'].items() if k not in ('boot/initrd.img', 'p1chksum')} == {k: v for k, v in after['files'].items() if k not in ('boot/initrd.img', 'p1chksum')}, 'Other FAT files changed')
    spans.sort(key=lambda x: x['offset'])
    cursor = 0
    for span in spans:
        a, n = (span['offset'], span['length'])
        require(a >= cursor and raw[cursor:a] == result[cursor:a], 'Overlapping ranges or unexpected changes')
        span.update(before_sha256=sha(raw[a:a + n]), after_sha256=sha(result[a:a + n]))
        cursor = a + n
    require(raw[cursor:] == result[cursor:], 'Unexpected p1 tail change')
    require(file_sha(source) == expected.lower(), 'Source changed during preparation')
    (out / 'p1_original.bin').write_bytes(raw)
    (out / 'p1_candidate.bin').write_bytes(result)
    manifest = dict(schema='m4-offline-p1-bundle/1', source=str(source), source_sha256=sha(raw), candidate_sha256=sha(result), bytes=len(raw), original='p1_original.bin', candidate='p1_candidate.bin', key_sha256=before['key_sha256'], public_key_unchanged=True, verifyKey_unchanged=True, strategy='SD_SIGNATURE_AND_VERSION_GATES_ORIGINAL_DAT_SIGNATURE', gates=dict(signature=dict(library=SD_GATE['library'], offset=SD_GATE['offset'], bytes=8, stub_hex=STUB.hex()), sd_version=dict(library=ver['library'], offset=ver['offset'], bytes=8, stub_hex=ver['stub_hex'], return_value=ver['return_value']), chkfirm=dict(library=CHK_GATE['library'], sites=cc_sites, patched_hex=[s['patched_hex'] for s in CHK_GATE['sites']])), spans=spans, before=before, after=after, profile_sha256=file_sha(Path(__file__).parent / 'm4_profile.json'), status='OFFLINE_ONLY', camera_io=False, current_body_verified=False, actual_changed_bytes=sum((a != b for a, b in zip(raw, result))), outside_spans_identical=True, metadata_preserved=True, already_adapted=new_initrd == initrd, live_writer_implemented=False)
    save_json(out / 'bundle.json', manifest)
    return manifest

def load_bundle(directory):
    directory = local_path(directory)
    m = json.loads(local_path(directory / 'bundle.json', existing=True).read_text('utf-8'))
    require(m['schema'] == 'm4-offline-p1-bundle/1' and m['original'] == 'p1_original.bin' and (m['candidate'] == 'p1_candidate.bin'), 'Unsupported bundle')
    require(m['profile_sha256'] == file_sha(Path(__file__).parent / 'm4_profile.json'), 'Bundle profile changed; rebuild and review')
    old = locked(directory / m['original'], m['source_sha256']).read_bytes()
    new = locked(directory / m['candidate'], m['candidate_sha256']).read_bytes()
    require(len(old) == len(new) == m['bytes'], 'Bundle lengths differ')
    cursor = 0
    for row in m['spans']:
        a, n = (row['offset'], row['length'])
        require(isinstance(a, int) and isinstance(n, int) and (cursor <= a < a + n <= len(old)), 'Invalid patch range')
        require(old[cursor:a] == new[cursor:a] and sha(old[a:a + n]) == row['before_sha256'] and (sha(new[a:a + n]) == row['after_sha256']), 'Bundle ranges do not match payload')
        cursor = a + n
    require(old[cursor:] == new[cursor:], 'Unlisted bundle changes')
    report = inspect_bytes(new)[0]
    baseline = inspect_bytes(old)[0]
    require(report['trust_state'] in ('downgrade_bypass', 'sd_signature_bypass') and report['key_sha256'] == m['key_sha256'] == baseline['key_sha256'] and (baseline['trust_state'] == m['before']['trust_state']), 'Invalid signature gate bundle')
    return (m, old, new)

def replay(directory, source, expected, direction, output):
    m, old, new = load_bundle(directory)
    p = locked(source, expected)
    actual = p.read_bytes()
    require(direction in ('apply', 'restore') and len(actual) == len(old), 'Invalid replay request')
    before, after = (old, new) if direction == 'apply' else (new, old)
    already_restored = direction == 'restore' and all((actual[r['offset']:r['offset'] + r['length']] == old[r['offset']:r['offset'] + r['length']] for r in m['spans']))
    require(direction != 'apply' or sha(actual) == m['source_sha256'], 'Apply baseline changed')
    for row in m['spans']:
        a, n = (row['offset'], row['length'])
        require(already_restored or actual[a:a + n] == before[a:a + n], 'Patch window changed; do not retry or restore blindly')
    result = bytearray(actual)
    for row in m['spans']:
        a, n = (row['offset'], row['length'])
        if not already_restored:
            result[a:a + n] = after[a:a + n]
    require(file_sha(p) == expected.lower(), 'Replay source changed')
    inspect_bytes(bytes(result))
    out = new_dir(output)
    target = out / ('p1_' + direction + '.bin')
    target.write_bytes(result)
    receipt = dict(direction=direction, input_sha256=sha(actual), output_sha256=file_sha(target), bytes=len(result), checked_windows=len(m['spans']), camera_io=False, outside_windows_preserved=True, exact_original_restored=bytes(result) == old, already_restored=already_restored, current_body_verified=False, status='LOCAL_FILE_REPLAY_ONLY')
    save_json(out / 'receipt.json', receipt)
    return receipt
