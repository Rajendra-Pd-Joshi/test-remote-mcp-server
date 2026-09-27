from contextlib import asynccontextmanager
from fastmcp import FastMCP

import os
import sqlite3
import aiosqlite
import tempfile
import json

from typing import Optional


# ============================================================
# FILE PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# In cloud:
#   Set DB_PATH to a persistent writable location.
#
# Locally:
#   Falls back to the system temporary directory.

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(tempfile.gettempdir(), "expenses.db"),
)

CATEGORIES_PATH = os.path.join(
    BASE_DIR,
    "categories.json",
)


# ============================================================
# DEFAULT CATEGORIES
# ============================================================

DEFAULT_CATEGORIES = {
    "categories": [
        "Food & Dining",
        "Transportation",
        "Shopping",
        "Entertainment",
        "Bills & Utilities",
        "Healthcare",
        "Travel",
        "Education",
        "Business",
        "Other",
    ]
}


print(f"[CONFIG] Database path: {DB_PATH}")


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db() -> None:
    """
    Create the expenses table and verify that the database
    is writable.
    """

    try:
        # Make sure the parent directory exists.
        db_directory = os.path.dirname(DB_PATH)

        if db_directory:
            os.makedirs(
                db_directory,
                exist_ok=True,
            )

        with sqlite3.connect(DB_PATH) as conn:

            conn.execute(
                "PRAGMA journal_mode=WAL"
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    date        TEXT    NOT NULL,
                    amount      REAL    NOT NULL,
                    category    TEXT    NOT NULL,
                    subcategory TEXT    DEFAULT '',
                    note        TEXT    DEFAULT ''
                )
                """
            )

            # Verify write access.
            conn.execute(
                """
                INSERT OR IGNORE INTO expenses
                (date, amount, category)
                VALUES ('2000-01-01', 0, 'test')
                """
            )

            conn.execute(
                """
                DELETE FROM expenses
                WHERE category = 'test'
                """
            )

            conn.commit()

        print(
            f"[OK] Database initialized at {DB_PATH}"
        )

    except Exception as e:

        print(
            f"[ERROR] Database initialization failed: {e}"
        )

        raise


# ============================================================
# SERVER LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(server: FastMCP):
    """
    Initialize the database when the server starts.
    """

    init_db()

    yield


# ============================================================
# CREATE MCP SERVER
# ============================================================

mcp = FastMCP(
    "ExpenseTracker",
    lifespan=lifespan,
)


# ============================================================
# TOOL 1: ADD EXPENSE
# ============================================================

@mcp.tool()
async def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
) -> dict:
    """
    Add a new expense to the database.

    Args:
        date: Expense date in YYYY-MM-DD format.
        amount: Expense amount.
        category: Main expense category.
        subcategory: Optional subcategory.
        note: Optional note about the expense.
    """

    try:

        async with aiosqlite.connect(
            DB_PATH
        ) as conn:

            await conn.execute(
                "PRAGMA journal_mode=WAL"
            )

            cursor = await conn.execute(
                """
                INSERT INTO expenses
                (
                    date,
                    amount,
                    category,
                    subcategory,
                    note
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    date,
                    amount,
                    category,
                    subcategory,
                    note,
                ),
            )

            await conn.commit()

            return {
                "status": "ok",
                "message": "Expense added successfully.",
                "id": cursor.lastrowid,
                "date": date,
                "amount": amount,
                "category": category,
                "subcategory": subcategory,
                "note": note,
            }

    except Exception as e:

        if "readonly" in str(e).lower():

            return {
                "status": "error",
                "error": (
                    "Database is read-only. "
                    "Check file permissions."
                ),
            }

        return {
            "status": "error",
            "error": str(e),
        }


# ============================================================
# TOOL 2: LIST EXPENSES
# ============================================================

@mcp.tool()
async def list_expenses(
    start_date: str,
    end_date: str,
) -> dict:
    """
    List expense entries within an inclusive date range.

    Args:
        start_date: Starting date in YYYY-MM-DD format.
        end_date: Ending date in YYYY-MM-DD format.
    """

    try:

        async with aiosqlite.connect(
            DB_PATH
        ) as conn:

            await conn.execute(
                "PRAGMA journal_mode=WAL"
            )

            cursor = await conn.execute(
                """
                SELECT
                    id,
                    date,
                    amount,
                    category,
                    subcategory,
                    note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date ASC, id ASC
                """,
                (
                    start_date,
                    end_date,
                ),
            )

            cols = [
                description[0]
                for description in cursor.description
            ]

            rows = [
                dict(zip(cols, row))
                for row in await cursor.fetchall()
            ]

            return {
                "status": "ok",
                "count": len(rows),
                "expenses": rows,
            }

    except Exception as e:

        return {
            "status": "error",
            "error": (
                f"Error listing expenses: {str(e)}"
            ),
        }


# ============================================================
# TOOL 3: SUMMARIZE EXPENSES
# ============================================================

@mcp.tool()
async def summarize(
    start_date: str,
    end_date: str,
    category: Optional[str] = None,
) -> dict:
    """
    Summarize expenses by category within an inclusive
    date range.

    Args:
        start_date: Starting date in YYYY-MM-DD format.
        end_date: Ending date in YYYY-MM-DD format.
        category: Optional category filter.
    """

    try:

        async with aiosqlite.connect(
            DB_PATH
        ) as conn:

            await conn.execute(
                "PRAGMA journal_mode=WAL"
            )

            query = """
                SELECT
                    category,
                    SUM(amount) AS total_amount,
                    COUNT(*) AS count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """

            params = [
                start_date,
                end_date,
            ]

            if category:

                query += """
                    AND category = ?
                """

                params.append(category)

            query += """
                GROUP BY category
                ORDER BY total_amount DESC
            """

            cursor = await conn.execute(
                query,
                params,
            )

            cols = [
                description[0]
                for description in cursor.description
            ]

            rows = [
                dict(zip(cols, row))
                for row in await cursor.fetchall()
            ]

            return {
                "status": "ok",
                "count": len(rows),
                "summary": rows,
            }

    except Exception as e:

        return {
            "status": "error",
            "error": (
                f"Error summarizing expenses: {str(e)}"
            ),
        }


# ============================================================
# TOOL 4: DATABASE DIAGNOSTICS
# ============================================================

@mcp.tool()
async def database_info() -> dict:
    """
    Check the SQLite database path, existence,
    filesystem permissions, and database connectivity.
    """

    directory = os.path.dirname(DB_PATH)

    result = {
        "db_path": DB_PATH,
        "db_exists": os.path.exists(DB_PATH),
        "directory": directory,
        "directory_writable": os.access(
            directory,
            os.W_OK,
        ),
    }

    # --------------------------------------------------------
    # Test connection
    # --------------------------------------------------------

    try:

        async with aiosqlite.connect(
            DB_PATH
        ) as conn:

            await conn.execute(
                "SELECT 1"
            )

        result["connection"] = "ok"

    except Exception as e:

        result["connection"] = (
            f"failed: {e}"
        )


    # --------------------------------------------------------
    # Test write access
    # --------------------------------------------------------

    try:

        async with aiosqlite.connect(
            DB_PATH
        ) as conn:

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                _write_test (
                    id INTEGER
                )
                """
            )

            await conn.commit()

            await conn.execute(
                """
                DROP TABLE IF EXISTS
                _write_test
                """
            )

            await conn.commit()

        result["write_access"] = "ok"

    except Exception as e:

        result["write_access"] = (
            f"failed: {e}"
        )

    return result


# ============================================================
# RESOURCE: CATEGORIES
# ============================================================

@mcp.resource(
    "expense:///categories",
    mime_type="application/json",
)
def categories() -> str:
    """
    Return available expense categories.
    """

    try:

        with open(
            CATEGORIES_PATH,
            "r",
            encoding="utf-8",
        ) as f:

            return f.read()

    except FileNotFoundError:

        return json.dumps(
            DEFAULT_CATEGORIES,
            indent=2,
        )

    except Exception as e:

        return json.dumps(
            {
                "error": str(e)
            }
        )


# ============================================================
# SERVER ENTRY POINT
# ============================================================

if __name__ == "__main__":

    mcp.run(
        transport=os.environ.get(
            "MCP_TRANSPORT",
            "http",
        ),
        host=os.environ.get(
            "HOST",
            "0.0.0.0",
        ),
        port=int(
            os.environ.get(
                "PORT",
                8000,
            )
        ),
    )

