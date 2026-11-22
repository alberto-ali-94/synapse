"""Local macOS runtime bundle for the script-launched Nova window."""
import os
from pathlib import Path
import plistlib
import shutil
import sys


def launch_in_app_bundle(script, *, name="Nova", identifier="local.synapse.nova"):
    """Re-exec the same Python in a named bundle before importing Cocoa."""
    if sys.platform != "darwin":
        return
    root = Path(script).resolve().parent
    contents = root / ".macos" / f"{name}.app" / "Contents"
    executable = contents / "MacOS" / name
    if Path(sys.executable).absolute() == executable:
        return
    source = Path(sys.executable).resolve()
    venv = Path(sys.prefix)
    config = venv / "pyvenv.cfg"
    if not config.is_file():
        raise RuntimeError("Start Nova with its .venv/bin/python interpreter")
    executable.parent.mkdir(parents=True, exist_ok=True)
    (contents / "lib").mkdir(exist_ok=True)
    # Copy only the small interpreter executable; reuse installed libraries.
    if not executable.exists() or source.stat().st_mtime_ns != executable.stat().st_mtime_ns or source.stat().st_size != executable.stat().st_size:
        shutil.copy2(source, executable)
    shutil.copy2(config, contents / "pyvenv.cfg")
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    links = {
        f"lib{version}.dylib": Path(sys.base_prefix) / "lib" / f"lib{version}.dylib",
        version: venv / "lib" / version,
    }
    for link_name, target in links.items():
        link = contents / "lib" / link_name
        if link.is_symlink() and link.readlink() != target:
            link.unlink()
        if not link.is_symlink():
            link.symlink_to(target)
    info = {
        "CFBundleName": name,
        "CFBundleDisplayName": name,
        "CFBundleExecutable": name,
        "CFBundleIdentifier": identifier,
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "Nova uses the microphone for voice conversations.",
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    os.execv(str(executable), [str(executable), str(Path(script).resolve()), *sys.argv[1:]])
