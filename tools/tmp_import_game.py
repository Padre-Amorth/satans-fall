import sys

sys.path.insert(0, ".")
try:
    print("import ok")
except Exception:
    import traceback

    traceback.print_exc()
