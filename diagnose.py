"""Run this from the same place you run main.py to diagnose the import issue."""
import os
import sys

print("=== Import Diagnostic ===")
print(f"Python:       {sys.executable}")
print(f"Version:      {sys.version}")
print(f"CWD:          {os.getcwd()}")
print(f"__file__:     {__file__}")
print(f"abspath:      {os.path.abspath(__file__)}")
print(f"dirname:      {os.path.dirname(os.path.abspath(__file__))}")
print()

script_dir = os.path.dirname(os.path.abspath(__file__))

print("=== Contents of script directory ===")
for item in sorted(os.listdir(script_dir)):
    full = os.path.join(script_dir, item)
    kind = "DIR " if os.path.isdir(full) else "FILE"
    print(f"  {kind}  {item}")

print()
print("=== Checking for required packages ===")
for pkg in ["ofcore", "oftemplates", "ofwidgets"]:
    pkg_path = os.path.join(script_dir, pkg)
    exists = os.path.isdir(pkg_path)
    has_init = os.path.isfile(os.path.join(pkg_path, "__init__.py")) if exists else False
    print(f"  {pkg}/           exists={exists}")
    print(f"  {pkg}/__init__.py exists={has_init}")

print()
print("=== Checking for OLD packages (should NOT exist) ===")
for pkg in ["core", "templates", "widgets"]:
    pkg_path = os.path.join(script_dir, pkg)
    exists = os.path.isdir(pkg_path)
    if exists:
        print(f"  WARNING: old '{pkg}/' directory still exists — delete it!")
    else:
        print(f"  {pkg}/  not found (good)")

print()
print("=== sys.path (first 10) ===")
for i, p in enumerate(sys.path[:10]):
    marker = " <-- script dir" if p == script_dir else ""
    print(f"  [{i}] {p}{marker}")

# Now try the fix and import
print()
print("=== Attempting import fix ===")
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
    print(f"  Inserted {script_dir} into sys.path[0]")
else:
    print(f"  Script dir already in sys.path at index {sys.path.index(script_dir)}")

try:
    import ofcore
    print(f"  ✓ import ofcore  ->  {ofcore.__file__}")
except ImportError as e:
    print(f"  ✗ import ofcore FAILED: {e}")

try:
    from ofcore.case_manager import CaseManager
    print(f"  ✓ from ofcore.case_manager import CaseManager")
except ImportError as e:
    print(f"  ✗ from ofcore.case_manager import CaseManager FAILED: {e}")

try:
    from oftemplates import simplefoam
    print(f"  ✓ from oftemplates import simplefoam")
except ImportError as e:
    print(f"  ✗ from oftemplates import simplefoam FAILED: {e}")

print()
print("=== Done ===")
