"""真实模型冒烟：默认被 pytest.ini 的 -m "not slow" 跳过。

执行：python -m pytest -m slow -q
"""
import math
import pathlib

import pytest

from app.core.config import settings
from app.integrations import embedding

pytestmark = pytest.mark.slow


def test_real_model_available_and_normalized():
    model = embedding.BgeEmbedder()
    vector = model.encode(["门锁没电了"])[0]
    assert len(vector) == settings.embedding_dim
    assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-6)


def test_model_files_land_in_hf_home():
    """首次加载后模型文件应落在 HF_HOME（默认 var/models）。"""
    embedding.BgeEmbedder().encode(["预热"])
    home = pathlib.Path(settings.hf_home).expanduser().resolve()
    assert home.is_dir()
    assert any(home.rglob("*.safetensors")) or any(home.rglob("*.bin"))
