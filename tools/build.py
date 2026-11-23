"""Build an allowlisted reproducible stdlib zip application. No install/network."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build():
    target = ROOT / "dist" / "agent-permission-clinic.pyz"
    target.parent.mkdir(exist_ok=True)
    entries = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in (ROOT / "clinic").glob("*.py")}
    entries["clinic/corpus.json"] = (ROOT / "clinic/corpus.json").read_bytes()
    for name in ("README.md", "LICENSE"):
        entries[name] = (ROOT / name).read_bytes()
    entries["__main__.py"] = b"from clinic.__main__ import main\nraise SystemExit(main())\n"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data.replace(b"\r\n", b"\n"))
    print(target.name, hashlib.sha256(target.read_bytes()).hexdigest())
    return target


if __name__ == "__main__":
    build()
