import os
import pytest

os.environ.setdefault("DATABASE_NAME", "hackathon_db")


@pytest.fixture(scope="session")
def app():
    from app import create_app
    from app.database import init_test_db
    from app.models.event import Event
    from app.models.url import URL
    from app.models.user import User

    _app = create_app(test_config={"TESTING": True, "CACHE_TYPE": "SimpleCache"})

    test_db = init_test_db()
    with _app.app_context():
        test_db.create_tables([User, URL, Event], safe=True)

    yield _app

    with _app.app_context():
        test_db.drop_tables([User, URL, Event])
    test_db.close()
    try:
        os.remove("/tmp/hackathon_test.db")
    except FileNotFoundError:
        pass


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db(app):
    yield
    from app.models.event import Event
    from app.models.url import URL
    from app.models.user import User

    with app.app_context():
        Event.delete().execute()
        URL.delete().execute()
        User.delete().execute()
