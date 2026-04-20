import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from budget_app.db.db import init_db, migrate_db, set_db_path


@pytest.fixture
def initialized_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    migrate_db()
    set_db_path(db_path)
    return db_path
