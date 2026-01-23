# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test wheel imports in a manylinux_2_28 compatible environment using podman."""

import os
import subprocess
import sys
from pathlib import Path


def get_pymomentum_modules() -> list[str]:
    """Dynamically discover all pymomentum submodules to test.

    Returns a list of module names that should be importable from pymomentum.
    This is determined by looking at the package structure.
    """
    # Core modules that are always expected (compiled C++ extensions)
    core_modules = [
        "pymomentum.geometry",
        "pymomentum.solver",
        "pymomentum.solver2",
        "pymomentum.marker_tracking",
        "pymomentum.axel",
    ]

    # Optional modules (may or may not be present depending on build options)
    optional_modules = [
        "pymomentum.torch",
        "pymomentum.tensor_ik",
        "pymomentum.tensor_momentum",
    ]

    return core_modules, optional_modules


def test_in_container(wheel_file: Path, wheel_type: str, py_ver: str) -> int:
    """Test wheel in a manylinux_2_28 container using podman."""
    print(f"Testing wheel in manylinux_2_28 container: {wheel_file.name}")

    # Torch index URL based on wheel type
    if wheel_type == "gpu":
        torch_index = "https://download.pytorch.org/whl/cu128"
    else:
        torch_index = "https://download.pytorch.org/whl/cpu"

    core_modules, optional_modules = get_pymomentum_modules()

    # Build the dynamic import test script
    import_test_code = (
        '''
import sys
import importlib
import pkgutil

def discover_and_test_modules():
    """Dynamically discover and test all pymomentum modules."""
    core_modules = '''
        + repr(core_modules)
        + """
    optional_modules = """
        + repr(optional_modules)
        + """

    print("=" * 60)
    print("Testing pymomentum imports in clean uv environment")
    print("=" * 60)

    # Test core modules (required)
    failed = []
    for module in core_modules:
        try:
            importlib.import_module(module)
            print(f"  ✓ {module}")
        except Exception as e:
            print(f"  ✗ {module}: {e}", file=sys.stderr)
            failed.append(module)

    # Test optional modules (not required to pass)
    print("\\nOptional modules:")
    for module in optional_modules:
        try:
            importlib.import_module(module)
            print(f"  ✓ {module}")
        except Exception as e:
            print(f"  ○ {module}: not available ({type(e).__name__})")

    # Discover additional submodules dynamically
    print("\\nDynamic module discovery:")
    try:
        import pymomentum
        for importer, modname, ispkg in pkgutil.walk_packages(
            pymomentum.__path__, prefix="pymomentum."
        ):
            if modname not in core_modules and modname not in optional_modules:
                try:
                    importlib.import_module(modname)
                    print(f"  ✓ {modname}")
                except Exception as e:
                    print(f"  ○ {modname}: {type(e).__name__}")
    except Exception as e:
        print(f"  Could not walk package: {e}")

    print("\\n" + "=" * 60)
    if failed:
        print(f"FAILED: {len(failed)} core module(s) failed to import")
        for m in failed:
            print(f"  - {m}")
        return 1
    else:
        print("SUCCESS: All core modules imported successfully")
        return 0

if __name__ == "__main__":
    sys.exit(discover_and_test_modules())
"""
    )

    # Container command to test the wheel
    # py_ver is like "cp312" or "cp313", so py_ver[2:] gives "312" or "313"
    py_tag = py_ver[2:]  # e.g., "312" or "313"
    container_script = f"""
set -e
PYTHON=/opt/python/cp{py_tag}-cp{py_tag}/bin/python

echo "Installing uv..."
$PYTHON -m pip install --quiet --root-user-action=ignore uv

echo "Creating virtual environment with Python {py_tag}..."
$PYTHON -m uv venv --python $PYTHON /tmp/test_venv

echo "Installing torch from {torch_index}..."
$PYTHON -m uv pip install --python /tmp/test_venv/bin/python "torch>=2.8.0,<2.9" --index-url {torch_index}

echo "Installing wheel..."
$PYTHON -m uv pip install --python /tmp/test_venv/bin/python /wheel/{wheel_file.name}

echo ""
echo "Testing imports..."
/tmp/test_venv/bin/python << 'IMPORT_TEST_EOF'
{import_test_code}
IMPORT_TEST_EOF
"""

    # Run the test in a manylinux_2_28 container
    result = subprocess.run(
        [
            "podman",
            "run",
            "--rm",
            "-v",
            f"{wheel_file.parent.absolute()}:/wheel:ro",
            "quay.io/pypa/manylinux_2_28_x86_64:latest",
            "/bin/bash",
            "-c",
            container_script,
        ],
        capture_output=False,
    )

    return result.returncode


def main():
    # Determine Python version and wheel type
    py_ver = f"cp{sys.version_info.major}{sys.version_info.minor}"
    env_name = os.environ.get("PIXI_ENVIRONMENT_NAME", "")
    wheel_type = "gpu" if "cuda" in env_name else "cpu"

    # Find the wheel file
    dist_dir = Path("dist")
    wheel_files = [
        f
        for f in dist_dir.iterdir()
        if f.name.startswith(f"pymomentum_{wheel_type}")
        and py_ver in f.name
        and f.name.endswith(".whl")
    ]

    if not wheel_files:
        print(f"✗ No wheel found for {wheel_type} {py_ver}", file=sys.stderr)
        sys.exit(1)

    wheel_file = wheel_files[0]

    # Test in container for Linux manylinux wheels
    if sys.platform == "linux" and "manylinux" in wheel_file.name:
        returncode = test_in_container(wheel_file, wheel_type, py_ver)
    else:
        # For non-manylinux wheels (macOS, Windows), test locally
        print(f"Testing wheel locally: {wheel_file.name}")
        # TODO: Implement local testing for non-Linux platforms
        print("Local testing not yet implemented for this platform")
        returncode = 0

    sys.exit(returncode)


if __name__ == "__main__":
    main()
