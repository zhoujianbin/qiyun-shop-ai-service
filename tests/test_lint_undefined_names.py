"""静态门禁：不允许出现"用到了没导入的名字"（F821）——上次它表现为线上 500。"""
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("ruff") is None, reason="未安装 ruff")
def test_no_undefined_names_in_backend():
    result = subprocess.run(
        ["ruff", "check", "--select", "F821", "app", "scripts", "eval"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"存在未定义名字：\n{result.stdout}"
