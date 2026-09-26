from fastmcp import FastMCP
import os
import sqlite3
from typing import Optional


# ============================================================
# FILE PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "expense.db")
CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")


# ============================================================
# CREATE MCP SERVER
# ============================================================

mcp = FastMCP("ExpenseTracker")


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db() -> None:
    """Create the expenses table if it does not already exist."""

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)

        conn.commit()


# Initialize database when server starts
init_db()


# ============================================================
# TOOL 1: ADD EXPENSE
# ============================================================

@mcp.tool()
def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = ""
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
        with sqlite3.connect(DB_PATH) as conn:

            cursor = conn.execute(
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
                    note
                )
            )

            conn.commit()

            return {
                "status": "ok",
                "message": "Expense added successfully.",
                "id": cursor.lastrowid,
                "date": date,
                "amount": amount,
                "category": category,
                "subcategory": subcategory,
                "note": note
            }

    except sqlite3.OperationalError as e:

        return {
            "status": "error",
            "error": str(e),
            "db_path": DB_PATH
        }


# ============================================================
# TOOL 2: LIST EXPENSES
# ============================================================

@mcp.tool()
def list_expenses(
    start_date: str,
    end_date: str
) -> list:
    """
    List expense entries within an inclusive date range.

    Args:
        start_date: Starting date in YYYY-MM-DD format.
        end_date: Ending date in YYYY-MM-DD format.
    """

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute(
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
                end_date
            )
        )

        columns = [
            description[0]
            for description in cursor.description
        ]

        rows = cursor.fetchall()

        return [
            dict(zip(columns, row))
            for row in rows
        ]


# ============================================================
# TOOL 3: SUMMARIZE EXPENSES
# ============================================================

@mcp.tool()
def summarize(
    start_date: str,
    end_date: str,
    category: Optional[str] = None
) -> list:
    """
    Summarize expenses by category within an inclusive date range.

    Args:
        start_date: Starting date in YYYY-MM-DD format.
        end_date: Ending date in YYYY-MM-DD format.
        category: Optional category filter.
    """

    with sqlite3.connect(DB_PATH) as conn:

        query = """
            SELECT
                category,
                SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
        """

        params = [
            start_date,
            end_date
        ]

        # Optional category filter
        if category:

            query += """
                AND category = ?
            """

            params.append(category)

        # Group by category
        query += """
            GROUP BY category
            ORDER BY category ASC
        """

        cursor = conn.execute(
            query,
            params
        )

        columns = [
            description[0]
            for description in cursor.description
        ]

        rows = cursor.fetchall()

        return [
            dict(zip(columns, row))
            for row in rows
        ]


# ============================================================
# TOOL 4: DATABASE DIAGNOSTICS
# ============================================================

@mcp.tool()
def database_info() -> dict:
    """
    Check the SQLite database path, existence,
    filesystem permissions, and database connectivity.
    """

    directory = os.path.dirname(DB_PATH)

    result = {
        "db_path": DB_PATH,
        "db_exists": os.path.exists(DB_PATH),
        "directory": directory,
        "directory_exists": os.path.exists(directory),
        "directory_writable": os.access(directory, os.W_OK),
    }

    # Test SQLite connection
    try:

        with sqlite3.connect(DB_PATH) as conn:

            conn.execute("SELECT 1")

        result["database_connection"] = "ok"

    except Exception as e:

        result["database_connection"] = "failed"
        result["error"] = str(e)

    # Test actual write operation
    try:

        with sqlite3.connect(DB_PATH) as conn:

            conn.execute(
                "CREATE TABLE IF NOT EXISTS _write_test (id INTEGER)"
            )

            conn.commit()

            conn.execute(
                "DROP TABLE IF EXISTS _write_test"
            )

            conn.commit()

        result["database_write"] = "ok"

    except Exception as e:

        result["database_write"] = "failed"
        result["write_error"] = str(e)

    return result


# ============================================================
# RESOURCE: CATEGORIES
# ============================================================

@mcp.resource(
    "expense://categories",
    mime_type="application/json"
)
def categories() -> str:
    """Return available expense categories."""

    try:

        with open(
            CATEGORIES_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    except FileNotFoundError:

        return '{"error": "categories.json not found"}'


# ============================================================
# START MCP SERVER
# ============================================================

if __name__ == "__main__":

    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000
    )