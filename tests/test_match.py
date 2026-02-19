from dealgoblin.match.fts_query import build_fts_query


def test_simple_include():
    assert build_fts_query(include=["lamp", "vintage"]) == "lamp AND vintage"


def test_include_and_exclude():
    assert build_fts_query(include=["lamp"], exclude=["broken"]) == "lamp NOT broken"


def test_multiple_exclude():
    q = build_fts_query(include=["lamp"], exclude=["broken", "cracked"])
    assert q == "lamp NOT broken NOT cracked"


def test_empty_include_returns_none():
    assert build_fts_query(include=[]) is None
