from pathlib import Path

def get_repo_root() -> Path:
    p = Path(__file__).resolve()
    while not (p / ".git").exists() and p != p.parent:
        p = p.parent
    return p