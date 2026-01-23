#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Test pymomentum imports with dynamic module discovery.

Usage:
    python scripts/test_import.py
    pixi run import_test
"""

import importlib
import pkgutil
import sys

# Core modules that MUST import successfully
CORE_MODULES = [
    "pymomentum.geometry",
    "pymomentum.solver",
    "pymomentum.solver2",
    "pymomentum.marker_tracking",
    "pymomentum.axel",
]


def discover_modules() -> list[str]:
    """Dynamically discover all pymomentum submodules."""
    try:
        import pymomentum

        return [
            name
            for _, name, _ in pkgutil.walk_packages(
                pymomentum.__path__, prefix="pymomentum."
            )
        ]
    except ImportError:
        return []


def main() -> int:
    """Test all pymomentum imports. Returns 0 on success, 1 on failure."""
    print("=" * 60)
    print("Testing pymomentum imports")
    print("=" * 60)

    failed = []

    # Test core modules (required)
    print("\nCore modules:")
    for module in CORE_MODULES:
        try:
            importlib.import_module(module)
            print(f"  ✓ {module}")
        except Exception as e:
            print(f"  ✗ {module}: {e}")
            failed.append(module)

    # Dynamic discovery
    print("\nDiscovered modules:")
    for module in discover_modules():
        if module not in CORE_MODULES:
            try:
                importlib.import_module(module)
                print(f"  ✓ {module}")
            except Exception:
                print(f"  ○ {module} (optional)")

    print("\n" + "=" * 60)
    if failed:
        print(f"FAILED: {len(failed)} core module(s) failed")
        return 1
    print("SUCCESS: All core modules imported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
