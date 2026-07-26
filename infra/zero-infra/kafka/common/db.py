import os
from urllib.parse import urlparse, unquote
import psycopg


def connect() -> "psycopg.Connection":
    u = urlparse(os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://"))
    return psycopg.connect(
        host=u.hostname, port=u.port, dbname=u.path.lstrip("/"),
        user=u.username, password=unquote(u.password),
    )
