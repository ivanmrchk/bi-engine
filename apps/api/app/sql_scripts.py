from sqlalchemy import Connection


def run_sql_script(connection: Connection, script: str) -> None:
    """Runs a multi-statement SQL script exactly as written, in the caller's transaction.

    Going straight to the driver's cursor, with no parameters, means a
    literal % in the SQL (as in LIKE '%x') isn't mistaken for a placeholder.
    """
    with connection.connection.cursor() as cursor:
        cursor.execute(script)
