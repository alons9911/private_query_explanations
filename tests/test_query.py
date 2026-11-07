import numpy as np
import pandas as pd
import pytest

from pqde.query import And, Atom, Or, TrueP, conjuncts, parse

DF = pd.DataFrame({"edu": ["Bachelors", "Masters", "HS", "Masters"], "h": [55, 30, 60, 50],
                   "inc": [1, 0, 1, 1]})


def test_paper_query():
    p = parse("education IN ('Bachelors','Masters') AND hoursPerWeek >= 50".replace("education", "edu").replace("hoursPerWeek", "h"))
    assert p.evaluate(DF).tolist() == [True, False, False, True]
    assert parse(p.to_sql()).evaluate(DF).tolist() == p.evaluate(DF).tolist()


@pytest.mark.parametrize("q,expected", [
    ("edu = 'Masters'", [False, True, False, True]),
    ("edu != 'Masters'", [True, False, True, False]),
    ("h < 50 OR inc = 0", [False, True, False, False]),
    ("NOT (h >= 50)", [False, True, False, False]),
    ("edu NOT IN ('HS') AND (h > 40 OR inc = 0)", [True, True, False, True]),
    ("inc = 1", [True, False, True, True]),
    ("TRUE", [True] * 4),
    ("", [True] * 4),
])
def test_eval(q, expected):
    assert parse(q).evaluate(DF).tolist() == expected


def test_conjuncts_and_attributes():
    p = parse("a = 1 AND b <= 2 AND c IN ('x', 'y')")
    assert len(conjuncts(p)) == 3
    assert p.attributes() == {"a", "b", "c"}
    assert conjuncts(TrueP()) == []
    assert isinstance(parse("a = 1 OR b = 2"), Or)


def test_quotes_roundtrip():
    p = parse("name = 'O''Brien'")
    assert p.value == "O'Brien"
    assert parse(p.to_sql()) == p


def test_syntax_errors():
    with pytest.raises(SyntaxError):
        parse("a = ")
    with pytest.raises(SyntaxError):
        parse("a = 1 b")
