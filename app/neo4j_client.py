import neo4j
from app.config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = neo4j.GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    return _driver


def run_query(query: str, params: dict | None = None):
    with get_driver().session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


def run_write(query: str, params: dict | None = None):
    with get_driver().session() as session:
        session.run(query, params or {})


def close():
    global _driver
    if _driver:
        _driver.close()
        _driver = None
