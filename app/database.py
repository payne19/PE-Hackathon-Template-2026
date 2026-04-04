import os

from peewee import DatabaseProxy, Model, PostgresqlDatabase, SqliteDatabase

db = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = db


def init_db(app):
    database = PostgresqlDatabase(
        os.environ.get("DATABASE_NAME", "hackathon_db"),
        host=os.environ.get("DATABASE_HOST", "localhost"),
        port=int(os.environ.get("DATABASE_PORT", 5432)),
        user=os.environ.get("DATABASE_USER", "postgres"),
        password=os.environ.get("DATABASE_PASSWORD", "postgres"),
    )
    db.initialize(database)

    @app.before_request
    def _db_connect():
        db.connect(reuse_if_open=True)

    @app.teardown_appcontext
    def _db_close(exc):
        if not db.is_closed():
            db.close()


def init_test_db(path: str = None) -> SqliteDatabase:
    """Initialize a file-based SQLite database for testing (no PostgreSQL needed)."""
    import tempfile
    if path is None:
        path = os.path.join(tempfile.gettempdir(), "hackathon_test.db")
    test_database = SqliteDatabase(path, pragmas={"foreign_keys": 1})
    db.initialize(test_database)
    return test_database
