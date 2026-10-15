"""Check the Git publication set, including the two intentionally public keys."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEYS = {"keys/published/A7M4_updater_private.pem", "keys/published/A7M4_updater_public.pem"}
BLOCKED = {".bin", ".img", ".uf2", ".dat", ".exe", ".dll", ".cat", ".pfx", ".p12", ".zip", ".7z", ".tar", ".so", ".key"}


def check():
    raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    paths = sorted(set(p.decode("utf-8") for p in raw.split(b"\0") if p))
    errors = []
    manifest = json.loads((ROOT / "keys/published/fingerprints.json").read_text("utf-8"))
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"Missing publication file: {relative}")
            continue
        data = path.read_bytes()
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            errors.append(f"Linked publication file: {relative}")
        if path.suffix.lower() in BLOCKED or relative.startswith(("vendor/local/", "local/", "runtime/", "backups/", "output/")):
            errors.append(f"Local/proprietary artifact in publication: {relative}")
        if relative in PUBLIC_KEYS:
            expected = manifest["files"][path.name]
            if hashlib.sha256(data).hexdigest() != expected:
                errors.append(f"Published key changed: {relative}")
            continue
        if path.suffix.lower() == ".pem" or re.search(rb"-----BEGIN (?:RSA |EC |ENCRYPTED |OPENSSH )?PRIVATE KEY-----", data):
            errors.append(f"Unexpected key material: {relative}")
        if path.suffix.lower() in (".py", ".md", ".json", ".toml", ".bat", ".cmd"):
            try:
                text = data.decode("utf-8")
            except UnicodeError:
                errors.append(f"Not UTF-8: {relative}")
                continue
            if "\ufffd" in text:
                errors.append(f"Replacement character: {relative}")
            if ("G:" + "/AIwork/") in text or ("G:" + "\\AIwork\\") in text:
                errors.append(f"Private workspace path: {relative}")
            if path.suffix.lower() == ".md":
                for link in re.findall(r"\]\(([^\s)]+)\)", text):
                    if "://" in link or link.startswith("#"):
                        continue
                    target = (path.parent / link.split("#")[0]).resolve()
                    if not target.is_relative_to(ROOT) or not target.exists():
                        errors.append(f"Broken local link in {relative}: {link}")
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    private = serialization.load_pem_private_key((ROOT / "keys/published/A7M4_updater_private.pem").read_bytes(), None)
    public = serialization.load_pem_public_key((ROOT / "keys/published/A7M4_updater_public.pem").read_bytes())
    if private.public_key().public_numbers() != public.public_numbers():
        errors.append("Published key pair does not match")
    der = public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if hashlib.sha256(der).hexdigest() != "eed3fd52e3adc60ef13b584bc0b50345ee96639be81efa02e0031a6eccc65e76":
        errors.append("Wrong published signing identity")
    challenge = b"a7m4-public-research-key-pair-check"
    signature = private.sign(challenge, padding.PKCS1v15(), hashes.SHA256())
    public.verify(signature, challenge, padding.PKCS1v15(), hashes.SHA256())
    if not PUBLIC_KEYS.issubset(paths):
        errors.append("The explicitly published pair must be included in Git")
    return {"files_checked": len(paths), "published_key_pair_verified": True, "errors": errors}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result["errors"]))
