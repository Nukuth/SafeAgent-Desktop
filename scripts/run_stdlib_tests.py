from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"

sys.path.insert(0, str(SRC))


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    passed = 0
    failed = 0
    for path in sorted(TESTS.glob("test_*.py")):
        module = load_module(path)
        for name in sorted(dir(module)):
            if not name.startswith("test_"):
                continue
            test_fn = getattr(module, name)
            if not callable(test_fn):
                continue
            try:
                if "tmp_path" in test_fn.__code__.co_varnames[: test_fn.__code__.co_argcount]:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        test_fn(Path(temp_dir))
                else:
                    test_fn()
            except Exception as exc:
                failed += 1
                print(f"FAIL {path.name}::{name}: {exc}")
            else:
                passed += 1
                print(f"PASS {path.name}::{name}")
    print(f"passed={passed} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

