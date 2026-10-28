"""Build source-only, disjoint team packages without touching working data."""

import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OWNERS = ("Shared", "Harsha", "Tharuka", "Ruvin")
SOURCE_DIRS = ("accounts", "cases", "config", "templates", "static", "locale", "docs", "tests", "tools")
SOURCE_FILES = (".env.example", ".gitignore", "AGENTS.md", "README.md", "manage.py",
                "requirements.txt", "package.json", "package-lock.json",
                "playwright.config.js", "sample_users.csv")
EXTENSIONS = {".py", ".html", ".txt", ".md", ".css", ".js", ".json", ".po", ".mo", ".ttf", ".png"}


def source_files():
    files = [ROOT / name for name in SOURCE_FILES]
    for directory in SOURCE_DIRS:
        for path in (ROOT / directory).rglob("*"):
            if "__pycache__" in path.parts:
                continue
            if path.is_symlink():
                raise ValueError(f"Refusing symlink: {path.relative_to(ROOT)}")
            if path.is_file() and path.suffix in EXTENSIONS:
                files.append(path)
    return sorted(files)


def build():
    ownership = json.loads((ROOT / "docs/team-ownership.json").read_text())
    paths = source_files()
    relative = {p.relative_to(ROOT).as_posix() for p in paths}
    if relative != set(ownership):
        raise ValueError(f"Update docs/team-ownership.json. Unassigned: {sorted(relative - set(ownership))}; missing: {sorted(set(ownership) - relative)}")
    if set(ownership.values()) - set(OWNERS):
        raise ValueError("Unknown owner")
    output = ROOT / "team-handoff"
    output.mkdir(exist_ok=True)
    contents = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
    manifest = {name: {"owner": ownership[name], "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in contents.items()}
    # Exclusive filenames keep previous handoffs intact. A fresh numbered directory
    # makes repeat runs safe without deleting or overwriting another handoff.
    number = 1
    while (output / f"handoff-{number:03d}").exists():
        number += 1
    destination = output / f"handoff-{number:03d}"
    destination.mkdir()
    groups = {owner: {n: d for n, d in contents.items() if ownership[n] == owner} for owner in OWNERS}
    groups["Complete-workspace"] = contents
    assembled = {}
    for owner, files in groups.items():
        archive_path = destination / f"{owner}.zip"
        instructions = (
            f"# {owner} handoff\n\n"
            "Read source/docs/team-workflow.md in Complete-workspace.zip first.\n\n"
            + ("This is the complete development reference. Create a fresh database using README.md.\n"
               "Do not submit this entire archive as one member's contribution.\n"
               if owner == "Complete-workspace" else
               "source/ contains only this package's allocated files and is not a standalone app.\n"
               "Shared + Harsha + Tharuka + Ruvin reconstruct the complete project.\n"
               "Use Complete-workspace.zip to run and test; consult the ownership manifest before editing shared files.\n")
            + "\nNo database, uploaded submissions, .env, backups, virtual environment or Git metadata is included.\n"
        )
        with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("START-HERE.md", instructions)
            archive.writestr("OWNERSHIP.json", json.dumps({n: manifest[n] for n in files}, indent=2) + "\n")
            for name, data in files.items():
                archive.writestr(f"source/{name}", data)
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip():
                raise ValueError(f"Corrupt archive: {archive_path}")
            for name, data in files.items():
                if archive.read(f"source/{name}") != data:
                    raise ValueError(f"Archive mismatch: {name}")
                if owner != "Complete-workspace":
                    if name in assembled:
                        raise ValueError(f"Overlapping ownership: {name}")
                    assembled[name] = data
        print(f"{owner}: {len(files)} source files -> {archive_path.relative_to(ROOT)}")
    if assembled != contents:
        raise ValueError("Packages do not reconstruct the complete source")
    (destination / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (destination / "START-HERE.md").write_text((ROOT / "docs/team-workflow.md").read_text())
    print(f"Verified: {len(contents)} files, no overlaps, byte-for-byte reconstruction.")


if __name__ == "__main__":
    build()
