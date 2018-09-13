"""Instrument pyodbc to report queries through ODBC.

``patch_all`` will automatically patch your pyodbc connection to make it work.
::

    from ddtrace import Pin, patch
    from pyodbc import connect

    # If not patched yet, you can patch pyodbc specifically
    patch(pyodbc=True)

    # This will report a span with the default settings
    dsn = "DSN=myDsn;UID=user;PWD=password"
    conn = connect(dsn)
    cursor = conn.cursor()
    cursor.execute("SELECT 1;")

    # Use a pin to specify metadata related to this connection
    Pin.override(conn, service='pyodbc-db')
"""

from ...utils.importlib import require_modules


required_modules = ['pyodbc']

with require_modules(required_modules) as missing_modules:
    if not missing_modules:
        from .patch import patch

        __all__ = ['patch']
