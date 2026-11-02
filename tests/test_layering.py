import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED = {"yfinance", "requests"}


def test_network_libraries_stay_in_desk_data():
    offenders = []
    for path in (ROOT / "desk").rglob("*.py"):
        if ROOT / "desk" / "data" in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            else:
                continue
            hit = names & BANNED
            if hit:
                offenders.append(f"{path.relative_to(ROOT)}: {sorted(hit)}")
    assert offenders == []
