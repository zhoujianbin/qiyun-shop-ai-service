#!/usr/bin/env python3
"""导出运行时 OpenAPI 契约（用于前端类型生成与契约核对）。"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

OUT = ROOT / "openapi.json"
OUT_YAML = ROOT / "openapi.yaml"


def main() -> None:
    spec = app.openapi()
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    paths = spec.get("paths", {})
    operations = sum(1 for item in paths.values() for m in item if m in ("get", "post", "put", "patch", "delete"))
    schemas = len(spec.get("components", {}).get("schemas", {}))
    try:
        import yaml

        OUT_YAML.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
        yaml_note = f" + {OUT_YAML.name}"
    except ImportError:
        yaml_note = ""
    print(f"openapi={spec.get('openapi')} paths={len(paths)} operations={operations} schemas={schemas} -> {OUT.name}{yaml_note}")


if __name__ == "__main__":
    main()
