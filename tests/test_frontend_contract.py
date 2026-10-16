"""前端契约一致性测试：前端集中声明的接口调用必须全部存在于后端运行时契约。"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_frontend_calls_match_runtime_contract():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_frontend_contract.py")],
                            capture_output=True, text=True, cwd=str(ROOT))
    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, "前端接口与后端契约不一致：\n" + output
    assert "problems=0" in output, output
