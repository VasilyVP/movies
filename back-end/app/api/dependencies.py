from __future__ import annotations

from typing import Annotated

import duckdb
from fastapi import Depends

from app.core.database import get_duckdb

DuckDBDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_duckdb)]
