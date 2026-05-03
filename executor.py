"""Script executor with support for Python, Batch, and SQL scripts."""
import subprocess
import sys
import tempfile
import os
import re
from datetime import datetime


def execute_script(script_code, script_type="python", timeout=60, variables=None, db_config=None):
    """
    Execute code in a separate subprocess with timeout.
    Supports: python, bat (batch/cmd), sql (via database connection).
    Variables dict replaces {{var_name}} placeholders in script_code.
    db_config dict: {sql_type, server, port, database, username, password}
    Returns (status, output, error).
    """
    if not script_code or not script_code.strip():
        return "failure", "", "No script code provided."

    # Substitute variables: replace {{var_name}} with value
    if variables:
        for name, value in variables.items():
            script_code = script_code.replace("{{" + name + "}}", value)

    executors = {
        "python": _execute_python,
        "bat": _execute_bat,
    }

    if script_type == "sql":
        return _execute_sql(script_code, timeout, db_config)

    executor_fn = executors.get(script_type, _execute_python)
    return executor_fn(script_code, timeout)


def _execute_python(script_code, timeout):
    """Execute Python code in a subprocess."""
    fd, script_path = tempfile.mkstemp(suffix=".py", prefix="task_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(script_code)

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
        )
        return _parse_result(result)

    except subprocess.TimeoutExpired:
        return "failure", "", f"Script timed out after {timeout} seconds."
    except Exception as e:
        return "failure", "", str(e)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def _execute_bat(script_code, timeout):
    """Execute Batch/CMD script in a subprocess."""
    fd, script_path = tempfile.mkstemp(suffix=".bat", prefix="task_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(script_code)

        result = subprocess.run(
            ["cmd.exe", "/c", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
        )
        return _parse_result(result)

    except subprocess.TimeoutExpired:
        return "failure", "", f"Script timed out after {timeout} seconds."
    except Exception as e:
        return "failure", "", str(e)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def _execute_sql(script_code, timeout, db_config=None):
    """Execute SQL script against a real database connection or SQLite in-memory fallback."""
    sql_type = (db_config or {}).get("sql_type", "sqlite")

    # Build a Python wrapper that connects and runs the SQL
    if sql_type == "mssql":
        wrapper = _build_mssql_wrapper(script_code, db_config)
    elif sql_type == "postgres":
        wrapper = _build_postgres_wrapper(script_code, db_config)
    elif sql_type == "mysql":
        wrapper = _build_mysql_wrapper(script_code, db_config)
    else:
        wrapper = _build_sqlite_wrapper(script_code)

    return _execute_python(wrapper, timeout)


def _build_mssql_wrapper(script_code, cfg):
    server = cfg.get("server", "localhost")
    port = cfg.get("port") or 1433
    database = cfg.get("database", "master")
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    win_auth = cfg.get("win_auth", False)
    import base64
    encoded_sql = base64.b64encode(script_code.encode()).decode()
    if win_auth:
        auth_part = '"Trusted_Connection=yes;"'
    else:
        auth_part = f'"UID={username};" "PWD={password};"'
    return f'''
import pyodbc
import base64
import sys
try:
    conn_str = (
        "DRIVER={{ODBC Driver 17 for SQL Server}};"
        "SERVER={server},{port};"
        "DATABASE={database};"
        {auth_part}
        "TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, timeout=10)
    cursor = conn.cursor()
    sql = base64.b64decode("{encoded_sql}").decode()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        try:
            cursor.execute(stmt)
            if cursor.description:
                cols = [d[0] for d in cursor.description]
                print(" | ".join(cols))
                print("-" * (len(" | ".join(cols))))
                for row in cursor.fetchall():
                    print(" | ".join(str(v) for v in row))
                print()
            else:
                print(f"{{cursor.rowcount}} row(s) affected")
        except Exception as e:
            print(f"ERROR: {{e}}")
    conn.commit()
    conn.close()
except Exception as e:
    print(f"Connection Error: {{e}}", file=sys.stderr)
    sys.exit(1)
'''


def _build_postgres_wrapper(script_code, cfg):
    server = cfg.get("server", "localhost")
    port = cfg.get("port") or 5432
    database = cfg.get("database", "postgres")
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    import base64
    encoded_sql = base64.b64encode(script_code.encode()).decode()
    return f'''
import psycopg2
import base64
import sys
try:
    conn = psycopg2.connect(
        host="{server}",
        port={port},
        dbname="{database}",
        user="{username}",
        password="{password}",
        connect_timeout=10
    )
    conn.autocommit = True
    cursor = conn.cursor()
    sql = base64.b64decode("{encoded_sql}").decode()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        try:
            cursor.execute(stmt)
            if cursor.description:
                cols = [d[0] for d in cursor.description]
                print(" | ".join(cols))
                print("-" * (len(" | ".join(cols))))
                for row in cursor.fetchall():
                    print(" | ".join(str(v) for v in row))
                print()
            else:
                print(f"{{cursor.rowcount}} row(s) affected")
        except Exception as e:
            print(f"ERROR: {{e}}")
    conn.close()
except Exception as e:
    print(f"Connection Error: {{e}}", file=sys.stderr)
    sys.exit(1)
'''


def _build_mysql_wrapper(script_code, cfg):
    server = cfg.get("server", "localhost")
    port = cfg.get("port") or 3306
    database = cfg.get("database", "")
    username = cfg.get("username", "root")
    password = cfg.get("password", "")
    import base64
    encoded_sql = base64.b64encode(script_code.encode()).decode()
    return f'''
import mysql.connector
import base64
import sys
try:
    conn = mysql.connector.connect(
        host="{server}",
        port={port},
        database="{database}",
        user="{username}",
        password="{password}",
        connection_timeout=10
    )
    cursor = conn.cursor()
    sql = base64.b64decode("{encoded_sql}").decode()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        try:
            cursor.execute(stmt)
            if cursor.description:
                cols = [d[0] for d in cursor.description]
                print(" | ".join(cols))
                print("-" * (len(" | ".join(cols))))
                for row in cursor.fetchall():
                    print(" | ".join(str(v) for v in row))
                print()
            else:
                print(f"{{cursor.rowcount}} row(s) affected")
        except Exception as e:
            print(f"ERROR: {{e}}")
    conn.commit()
    conn.close()
except Exception as e:
    print(f"Connection Error: {{e}}", file=sys.stderr)
    sys.exit(1)
'''


def _build_sqlite_wrapper(script_code):
    import base64
    encoded_sql = base64.b64encode(script_code.encode()).decode()
    return f'''
import sqlite3
import base64
conn = sqlite3.connect(":memory:")
cursor = conn.cursor()
sql = base64.b64decode("{encoded_sql}").decode()
statements = [s.strip() for s in sql.split(";") if s.strip()]
for stmt in statements:
    try:
        cursor.execute(stmt)
        if cursor.description:
            cols = [d[0] for d in cursor.description]
            print(" | ".join(cols))
            print("-" * (len(" | ".join(cols))))
            for row in cursor.fetchall():
                print(" | ".join(str(v) for v in row))
            print()
        elif cursor.rowcount >= 0:
            print(f"{{cursor.rowcount}} row(s) affected")
    except Exception as e:
        print(f"ERROR: {{e}}")
conn.commit()
conn.close()
'''


def test_db_connection(db_config):
    """Test a database connection and return (success, message)."""
    sql_type = db_config.get("sql_type", "sqlite")
    server = db_config.get("server", "localhost")
    port = db_config.get("port")
    database = db_config.get("database", "")
    username = db_config.get("username", "")
    password = db_config.get("password", "")

    win_auth = db_config.get("win_auth", False)

    if sql_type == "mssql":
        if win_auth:
            auth_part = '"Trusted_Connection=yes;"'
        else:
            auth_part = f'"UID={username};" "PWD={password};"'
        wrapper = f'''
import pyodbc
try:
    conn_str = (
        "DRIVER={{ODBC Driver 17 for SQL Server}};"
        "SERVER={server},{port or 1433};"
        "DATABASE={database or 'master'};"
        {auth_part}
        "TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, timeout=10)
    cursor = conn.cursor()
    cursor.execute("SELECT @@VERSION")
    print(cursor.fetchone()[0])
    conn.close()
    print("\\n[OK] Connection successful!")
except Exception as e:
    print(f"[FAIL] Connection failed: {{e}}")
'''
    elif sql_type == "postgres":
        wrapper = f'''
import psycopg2
try:
    conn = psycopg2.connect(
        host="{server}",
        port={port or 5432},
        dbname="{database or 'postgres'}",
        user="{username}",
        password="{password}",
        connect_timeout=10
    )
    cursor = conn.cursor()
    cursor.execute("SELECT version()")
    print(cursor.fetchone()[0])
    conn.close()
    print("\\n[OK] Connection successful!")
except Exception as e:
    print(f"[FAIL] Connection failed: {{e}}")
'''
    elif sql_type == "mysql":
        wrapper = f'''
import mysql.connector
try:
    conn = mysql.connector.connect(
        host="{server}",
        port={port or 3306},
        database="{database}",
        user="{username or 'root'}",
        password="{password}",
        connection_timeout=10
    )
    cursor = conn.cursor()
    cursor.execute("SELECT VERSION()")
    print(cursor.fetchone()[0])
    conn.close()
    print("\\n[OK] Connection successful!")
except Exception as e:
    print(f"[FAIL] Connection failed: {{e}}")
'''
    else:
        return "success", "SQLite in-memory -- no connection needed. [OK]"

    status, output, error = _execute_python(wrapper, timeout=15)
    combined = (output + "\n" + error).strip()
    if "[OK]" in combined:
        return "success", combined
    else:
        return "failure", combined


def _parse_result(result):
    """Parse subprocess result into (status, output, error) tuple."""
    output = result.stdout
    error = result.stderr
    if result.returncode == 0:
        return "success", output, error
    else:
        return "failure", output, error
