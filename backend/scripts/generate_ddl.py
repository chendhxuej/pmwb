from sqlalchemy import create_mock_engine
from sqlalchemy.schema import CreateTable

from db.base import Base
from db.models import *  # noqa: F401,F403


def dump(sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))


engine = create_mock_engine("mysql+pymysql://", dump)

for table in Base.metadata.sorted_tables:
    print(CreateTable(table).compile(dialect=engine.dialect))
    print()
