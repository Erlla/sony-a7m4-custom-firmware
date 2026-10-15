"""Build per-camera images. Never load a distributed camera partition image."""
import copy
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile
import tempfile
from .common import require, ToolError, digest, read_json, run
from .fat import Fat

SYMBOL = "_ZN7Updater21SignatureVerification9verifyKeyEPKc"
STUB = bytes.fromhex("00008052c0035fd6")
LIBS = ("libsdfileinputupdaterapi.so", "libseninputupdaterapi.so", "libupdaterapi.so", "libuudfileinputupdaterapi.so")
KEY_PATH = "etc/VerificationKey.pem"


def profiles():
    return read_json(Path(__file__).parent / "profiles" / "updater.json")


def elf_function(data):
    from elftools.elf.elffile import ELFFile
    try:
        elf = ELFFile(io.BytesIO(data))
        require(elf.elfclass == 64 and elf.little_endian and elf["e_machine"] == "EM_AARCH64", "ELF", "Expected little-endian AArch64 ELF")
        section = elf.get_section_by_name(".dynsym")
        require(section is not None, "UNSUPPORTED_UPDATER", "Updater has no dynamic symbols")
        matches = [s for s in section.iter_symbols() if s.name == SYMBOL and s["st_shndx"] != "SHN_UNDEF"]
        require(len(matches) == 1, "UNSUPPORTED_UPDATER", "Expected exactly one verifyKey function")
        sym = matches[0]
        require(sym["st_info"]["type"] == "STT_FUNC" and 8 <= sym["st_size"] <= 65536 and sym["st_value"] % 4 == 0, "ELF", "Invalid verifyKey function")
        loads = [s for s in elf.iter_segments() if s["p_type"] == "PT_LOAD" and s["p_flags"] & 1 and s["p_vaddr"] <= sym["st_value"] and sym["st_value"]+sym["st_size"] <= s["p_vaddr"]+s["p_filesz"]]
        require(len(loads) == 1, "ELF", "Function is not uniquely inside an executable segment")
        off = loads[0]["p_offset"] + sym["st_value"] - loads[0]["p_vaddr"]
        size = sym["st_size"]
        require(off+size <= len(data), "ELF", "Truncated function")
        return off, size
    except ToolError:
        raise
    except Exception as e:
        raise ToolError("ELF", f"Invalid ELF: {e}") from e


def patch_library(data, name):
    off, size = elf_function(data)
    function = data[off:off+size]
    allowed = profiles()["functions"].get(name, [])
    require(digest(function) in allowed, "UNSUPPORTED_UPDATER", f"Unverified verifyKey implementation in {name}: {digest(function)}", "Keep the backup; add a reviewed compatibility profile before unlocking this firmware.")
    output = bytearray(data)
    output[off:off+8] = STUB
    require(output[:off] == data[:off] and output[off+8:] == data[off+8:], "PATCH", "Unexpected ELF changes")
    return bytes(output), {"library": name, "symbol": SYMBOL, "offset": off, "size": size, "function_sha256": digest(function), "original_entry": data[off:off+8].hex()}


def public_key(pem):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    require(b"PRIVATE KEY" not in pem, "KEY", "Supply a public key only")
    try:
        key = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError) as e:
        raise ToolError("KEY", "Invalid PEM public key") from e
    require(isinstance(key, rsa.RSAPublicKey) and key.key_size == 2048 and key.public_numbers().e == 65537, "KEY", "Expected RSA-2048 public key, exponent 65537")
    normalized = key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    der = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return normalized, digest(der)


def new_keypair(directory):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    private, public = directory / "updater-private.pem", directory / "updater-public.pem"
    require(not private.exists() and not public.exists(), "EXISTS", "Key files already exist; never overwrite a signing identity")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with private.open("xb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    with public.open("xb") as f:
        f.write(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    try:
        private.chmod(0o600)
    except OSError:
        pass
    return {"public_key": str(public), "private_key": str(private), "fingerprint": public_key(public.read_bytes())[1]}


def version(image):
    value = Fat(image).read("updater/dat4")
    require(len(value) == 2, "VERSION", "dat4 must contain exactly two bytes")
    require(all((b >> 4) <= 9 and (b & 15) <= 9 for b in value),
            "VERSION", "dat4 contains invalid BCD; do not overwrite an unknown format")
    minor, major = ((b >> 4) * 10 + (b & 15) for b in value)
    return f"{major}.{minor:02d}"


def set_version(image, value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9]\.[0-9]{2}", value), "VERSION", "Use X.YY, major 0..9, for example 6.02 or 0.00")
    major, minor = map(int, value.split("."))
    fs = Fat(image)
    old = version(image)
    fs.replace("updater/dat4", bytes([((minor // 10) << 4) | (minor % 10), major]))
    output = fs.bytes()
    changes = sum(a != b for a, b in zip(image, output))
    require(changes <= 2 and len(image) == len(output) and version(output) == value, "VERSION_VERIFY", "Version patch validation failed")
    return output, {"old_version": old, "new_version": value, "changed_bytes": changes}


def _tar_name(name):
    name = name.removeprefix("./")
    require(not name.startswith("/") and ".." not in PurePosixPath(name).parts, "TAR", "Unsafe archive member path")
    return name.rstrip("/")


class Updater:
    def __init__(self, assets):
        self.assets = assets

    def _to_tar(self, image, temp):
        require(image[:4] == b"hsqs" and len(image) >= 96, "SQUASHFS", "Expected SquashFS initrd")
        block = struct.unpack_from("<I", image, 12)[0]
        compression, _, flags, _, major, minor = struct.unpack_from("<6H", image, 20)
        require(compression == 1 and (major, minor) == (4, 0) and 4096 <= block <= 1048576 and block & (block-1) == 0, "SQUASHFS", "Unsupported SquashFS format (requires v4 gzip)")
        require(struct.unpack_from("<Q", image, 56)[0] == 0xffffffffffffffff, "SQUASHFS_XATTR", "SquashFS extended attributes need a separately reviewed preservation path")
        Path(temp, "initrd.img").write_bytes(image)
        with Path(temp, "original.tar").open("wb") as stream:
            run([self.assets.get("squashfs/sqfs2tar.exe"), "initrd.img"], cwd=temp, stdout=stream)
        return block, flags

    def inspect(self, image):
        fs = Fat(image)
        initrd = fs.read("boot/initrd.img")
        checksum = fs.read("p1chksum")
        require(hashlib.md5(initrd).hexdigest().encode() in checksum, "CHECKSUM", "Original initrd/p1chksum disagree")
        with tempfile.TemporaryDirectory(prefix="a7m4-sqfs-") as temp:
            self._to_tar(initrd, temp)
            with tarfile.open(Path(temp, "original.tar")) as archive:
                members = {}
                for m in archive:
                    name = _tar_name(m.name)
                    require(name not in members, "TAR", "Duplicate archive member")
                    members[name] = m
                wanted = [KEY_PATH] + ["usr/lib/"+n for n in LIBS]
                data = {}
                for name in wanted:
                    m = members.get(name)
                    require(m and m.isfile() and 0 < m.size < 8*1024*1024, "UPDATER", f"Missing or invalid updater file: {name}")
                    data[name] = archive.extractfile(m).read()
                _, fingerprint = public_key(data[KEY_PATH])
                unmodified = True
                details = []
                for name in LIBS:
                    content = data["usr/lib/"+name]
                    off, size = elf_function(content)
                    supported = digest(content[off:off+size]) in profiles()["functions"].get(name, [])
                    unmodified &= supported
                    details.append({"library": name, "supported": supported, "patched": content[off:off+8] == STUB})
                return {"key_fingerprint": fingerprint, "official": fingerprint in profiles()["official_keys"] and unmodified, "libraries": details, "initrd_sha256": digest(initrd)}

    def validate_official_restore(self, current, original):
        """Do not restore an older kernel/updater merely because it has Sony's key."""
        require(self.inspect(original)["official"], "NO_OFFICIAL_BACKUP", "Selected backup does not contain a recognized official updater")
        if current == original:
            return
        def outside_payload(image):
            fs = Fat(image)
            for name in ("boot/initrd.img", "p1chksum"):
                off, cluster, _, _ = fs.locate(name)
                for c in fs.chain(cluster):
                    pos = fs.offset(c)
                    fs.data[pos:pos+fs.cluster_size] = bytes(fs.cluster_size)
                fs.data[off+28:off+32] = bytes(4)
            return fs.bytes()
        require(outside_payload(current) == outside_payload(original), "OFFICIAL_VERSION_MISMATCH", "Official backup differs outside updater/checksum; it may be from another firmware release")
        def logical_files(image):
            fs = Fat(image)
            content = {}
            with tempfile.TemporaryDirectory(prefix="a7m4-base-") as temp:
                self._to_tar(fs.read("boot/initrd.img"), temp)
                with tarfile.open(Path(temp, "original.tar")) as archive:
                    for member in archive:
                        name = _tar_name(member.name)
                        require(name not in content, "TAR", "Duplicate member")
                        value = archive.extractfile(member).read() if member.isfile() else None
                        if name == KEY_PATH:
                            public_key(value)
                            value = b"PUBLIC-KEY-SLOT"
                        elif name in ["usr/lib/"+n for n in LIBS]:
                            off, size = elf_function(value)
                            known = digest(value[off:off+size]) in profiles()["functions"].get(PurePosixPath(name).name, [])
                            require(known or value[off:off+8] == STUB, "UNSUPPORTED_UPDATER", "Unrecognized current updater patch")
                            value = value[:off]+bytes(8)+value[off+8:]
                        content[name] = (member.mode, member.uid, member.gid, member.mtime, member.type, member.linkname, member.devmajor, member.devminor, member.pax_headers, digest(value) if value is not None else None)
            return content
        require(logical_files(current) == logical_files(original), "OFFICIAL_VERSION_MISMATCH", "Official backup does not match the current updater files except for the allowed key/verifyKey changes", "Select the pre-unlock backup from the same firmware release, or use deliberate partition recovery with a complete matching set.")

    def unlock(self, image, pem):
        normalized, fingerprint = public_key(pem)
        require(fingerprint not in profiles()["official_keys"], "KEY", "Use your own public signing key")
        state = self.inspect(image)
        require(state["official"], "OFFICIAL_BASE_REQUIRED", "Unlock requires a recognized unmodified updater backup", "Restore a verified original backup from this camera before unlocking again.")
        fs = Fat(image)
        original = fs.read("boot/initrd.img")
        checksum = fs.read("p1chksum")
        evidence, changes = [], {KEY_PATH: normalized}
        with tempfile.TemporaryDirectory(prefix="a7m4-patch-") as temp:
            block, flags = self._to_tar(original, temp)
            with tarfile.open(Path(temp, "original.tar")) as src, tarfile.open(Path(temp, "modified.tar"), "w", format=tarfile.PAX_FORMAT) as dst:
                for item in src:
                    name = _tar_name(item.name)
                    data = src.extractfile(item).read() if item.isfile() else None
                    if name in ["usr/lib/"+n for n in LIBS]:
                        data, info = patch_library(data, PurePosixPath(name).name)
                        changes[name] = data
                        evidence.append(info)
                    elif name == KEY_PATH:
                        data = normalized
                    member = copy.copy(item)
                    if data is not None:
                        member.size = len(data)
                    dst.addfile(member, io.BytesIO(data) if data is not None else None)
            require(len(evidence) == 4, "PATCH", "All four updater libraries must be patched")
            args = [self.assets.get("squashfs/tar2sqfs.exe"), "-c", "gzip", "-b", str(block)]
            if flags & 0x80:
                args.append("--exportable")
            args.append("new.img")
            with Path(temp, "modified.tar").open("rb") as src:
                run(args, cwd=temp, stdin=src)
            rebuilt = Path(temp, "new.img").read_bytes()
            # Round-trip the rebuilt image and compare every file and POSIX metadata.
            with Path(temp, "roundtrip.tar").open("wb") as dst:
                run([self.assets.get("squashfs/sqfs2tar.exe"), "new.img"], cwd=temp, stdout=dst)
            def inventory(path):
                entries = {}
                with tarfile.open(path) as tf:
                    for m in tf:
                        name = _tar_name(m.name)
                        require(name not in entries, "TAR", "Duplicate member")
                        content = tf.extractfile(m).read() if m.isfile() else None
                        entries[name] = (m.mode, m.uid, m.gid, m.mtime, m.type, m.linkname, m.devmajor, m.devminor, m.pax_headers, digest(content) if content is not None else None)
                return entries
            require(inventory(Path(temp, "modified.tar")) == inventory(Path(temp, "roundtrip.tar")), "SQUASHFS_VERIFY", "Rebuilt filesystem changed file data or POSIX metadata")
        old_md5 = hashlib.md5(original).hexdigest().encode()
        require(checksum.count(old_md5) == 1, "CHECKSUM", "Ambiguous initrd checksum record")
        fs.replace("boot/initrd.img", rebuilt)
        fs.replace("p1chksum", checksum.replace(old_md5, hashlib.md5(rebuilt).hexdigest().encode()))
        output = fs.bytes()
        require(len(output) == len(image), "PATCH", "Partition size changed")
        return output, {"source": state, "public_key_fingerprint": fingerprint, "libraries": evidence, "initrd_sha256": digest(rebuilt)}
