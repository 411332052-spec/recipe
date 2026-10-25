"""每個模組都至少被載入一次，免得語法錯誤躲過其他測試（例如只在啟動時才會載入的 main.py）。"""

import importlib
import pkgutil

import recipe_agent


def test_every_module_imports():
    names = [m.name for m in pkgutil.iter_modules(recipe_agent.__path__)]
    assert {"main", "bot", "worker", "config", "claude_runner", "photo_store", "record_store"} <= set(names)
    for name in names:
        if name == "__main__":  # 載入它會直接啟動 agent
            continue
        importlib.import_module(f"recipe_agent.{name}")
