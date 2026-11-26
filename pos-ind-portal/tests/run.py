"""Runner tes tanpa dependensi (pytest tidak wajib). Pemakaian: python tests/run.py [modul ...]"""
import importlib, inspect, sys, traceback, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
mods = sys.argv[1:] or ["test_api"]
ok = bad = 0
for m in mods:
    mod = importlib.import_module(m)
    for name, fn in sorted(vars(mod).items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        args = inspect.signature(fn).parameters
        try:
            app = mod.make_app() if ("app" in args or "cl" in args) else None
            kw = {}
            if "app" in args: kw["app"] = app
            if "cl" in args: kw["cl"] = mod.C(app)
            fn(**kw)
            print("PASS", name); ok += 1
        except Exception:
            print("FAIL", name); traceback.print_exc(limit=4); bad += 1
print(f"\n{ok} lulus, {bad} gagal"); sys.exit(1 if bad else 0)
