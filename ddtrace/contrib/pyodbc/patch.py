# 3p
import wrapt
import pyodbc

# project
from ddtrace import Pin
from ddtrace.contrib.dbapi import TracedConnection
from ...ext import net, db, AppTypes

def patch():
    wrapt.wrap_function_wrapper('pyodbc', 'connect', _connect)


def unpatch():
    if isinstance(pyodbc.connect, wrapt.ObjectProxy):
        pyodbc.connect = pyodbc.connect.__wrapped__


def _connect(func, instance, args, kwargs):
    conn = func(*args, **kwargs)
    return patch_conn(conn)


def patch_conn(conn):
    pin = Pin(service="pyodbc", app="pyodbc", app_type=AppTypes.db, tags=tags)

    # grab the metadata from the conn
    wrapped = TracedConnection(conn, pin=pin)
    pin.onto(wrapped)
    return wrapped
