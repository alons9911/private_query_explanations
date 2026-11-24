"""A small SQL-WHERE predicate language (Section 2.1 of the paper).

Queries in the paper are ``SELECT agg(A) FROM D WHERE phi`` where ``phi`` is a
Boolean combination of atomic conditions: numerical comparisons
(``A <= c``), categorical equality (``A = v``) and set membership
(``A IN (v1, v2)``).  The framework only ever needs the *population*
``Q(D) = sigma_phi(D)``, so a query is represented here by its predicate.

Grammar (case-insensitive keywords)::

    expr   := term ( OR term )*
    term   := factor ( AND factor )*
    factor := NOT factor | '(' expr ')' | atom
    atom   := IDENT op value
            | IDENT [NOT] IN '(' value (',' value)* ')'
    op     := = | == | != | <> | < | <= | > | >=
    value  := 'quoted' | "quoted" | number | bareword

Example::

    >>> p = parse("education IN ('Bachelors','Masters') AND hoursPerWeek >= 50")
    >>> mask = p.evaluate(df)          # boolean numpy array over the rows of df
    >>> p.to_sql()
    "education IN ('Bachelors', 'Masters') AND hoursPerWeek >= 50"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

__all__ = [
    "Predicate",
    "Atom",
    "And",
    "Or",
    "Not",
    "TrueP",
    "parse",
    "conjuncts",
]

_NUM_OPS = {"<", "<=", ">", ">="}
_EQ_OPS = {"=", "!="}


def _fmt_value(v) -> str:
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return repr(float(v)) if not float(v).is_integer() else str(int(v))
    return "'" + str(v).replace("'", "''") + "'"


def _as_number(v):
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class Predicate:
    """Base class of predicate AST nodes."""

    def evaluate(self, df: pd.DataFrame) -> np.ndarray:  # pragma: no cover - abstract
        raise NotImplementedError

    def to_sql(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def attributes(self) -> set[str]:  # pragma: no cover - abstract
        raise NotImplementedError

    def __str__(self) -> str:
        return self.to_sql()

    def __and__(self, other: "Predicate") -> "Predicate":
        return And([self, other])

    def __or__(self, other: "Predicate") -> "Predicate":
        return Or([self, other])


@dataclass(frozen=True)
class TrueP(Predicate):
    """The empty predicate (selects everything)."""

    def evaluate(self, df: pd.DataFrame) -> np.ndarray:
        return np.ones(len(df), dtype=bool)

    def to_sql(self) -> str:
        return "TRUE"

    def attributes(self) -> set[str]:
        return set()


@dataclass(frozen=True)
class Atom(Predicate):
    """An atomic condition ``attr op value``; ``op`` in {=,!=,<,<=,>,>=,IN,NOT IN}."""

    attr: str
    op: str
    value: object  # scalar, or tuple of scalars for IN / NOT IN

    def evaluate(self, df: pd.DataFrame) -> np.ndarray:
        if self.attr not in df.columns:
            raise KeyError(f"unknown attribute {self.attr!r}; columns are {list(df.columns)}")
        col = df[self.attr]
        if self.op in _NUM_OPS:
            x = pd.to_numeric(col, errors="coerce").to_numpy(dtype=float)
            c = _as_number(self.value)
            if c is None:
                raise ValueError(f"non-numeric constant in {self.to_sql()}")
            with np.errstate(invalid="ignore"):
                if self.op == "<":
                    out = x < c
                elif self.op == "<=":
                    out = x <= c
                elif self.op == ">":
                    out = x > c
                else:
                    out = x >= c
            return np.asarray(out & ~np.isnan(x), dtype=bool)
        if self.op in ("IN", "NOT IN"):
            vals = list(self.value)
        else:
            vals = [self.value]
        out = _match_values(col, vals)
        if self.op in ("!=", "NOT IN"):
            out = ~out & col.notna().to_numpy()
        return out

    def to_sql(self) -> str:
        if self.op in ("IN", "NOT IN"):
            inner = ", ".join(_fmt_value(v) for v in self.value)
            return f"{self.attr} {self.op} ({inner})"
        return f"{self.attr} {self.op} {_fmt_value(self.value)}"

    def attributes(self) -> set[str]:
        return {self.attr}

    @property
    def values(self) -> tuple:
        """The constant(s) of the atom as a tuple."""
        return tuple(self.value) if self.op in ("IN", "NOT IN") else (self.value,)


def _match_values(col: pd.Series, vals: Sequence) -> np.ndarray:
    """Equality / membership test that works for numeric and string columns."""
    if pd.api.types.is_numeric_dtype(col):
        nums = [_as_number(v) for v in vals]
        if all(n is not None for n in nums):
            return col.isin(nums).to_numpy()
    as_str = col.astype("string")
    return as_str.isin([str(v) for v in vals]).fillna(False).to_numpy(dtype=bool)


@dataclass(frozen=True)
class And(Predicate):
    parts: tuple = field(default_factory=tuple)

    def __init__(self, parts: Iterable[Predicate]):
        flat: list[Predicate] = []
        for p in parts:
            if isinstance(p, And):
                flat.extend(p.parts)
            elif isinstance(p, TrueP):
                continue
            else:
                flat.append(p)
        object.__setattr__(self, "parts", tuple(flat))

    def evaluate(self, df: pd.DataFrame) -> np.ndarray:
        out = np.ones(len(df), dtype=bool)
        for p in self.parts:
            out &= p.evaluate(df)
        return out

    def to_sql(self) -> str:
        if not self.parts:
            return "TRUE"
        return " AND ".join(p.to_sql() if not isinstance(p, Or) else f"({p.to_sql()})" for p in self.parts)

    def attributes(self) -> set[str]:
        return set().union(*(p.attributes() for p in self.parts)) if self.parts else set()


@dataclass(frozen=True)
class Or(Predicate):
    parts: tuple = field(default_factory=tuple)

    def __init__(self, parts: Iterable[Predicate]):
        flat: list[Predicate] = []
        for p in parts:
            flat.extend(p.parts if isinstance(p, Or) else [p])
        object.__setattr__(self, "parts", tuple(flat))

    def evaluate(self, df: pd.DataFrame) -> np.ndarray:
        out = np.zeros(len(df), dtype=bool)
        for p in self.parts:
            out |= p.evaluate(df)
        return out

    def to_sql(self) -> str:
        return " OR ".join(p.to_sql() if not isinstance(p, And) else f"({p.to_sql()})" for p in self.parts)

    def attributes(self) -> set[str]:
        return set().union(*(p.attributes() for p in self.parts)) if self.parts else set()


@dataclass(frozen=True)
class Not(Predicate):
    part: Predicate

    def evaluate(self, df: pd.DataFrame) -> np.ndarray:
        return ~self.part.evaluate(df)

    def to_sql(self) -> str:
        return f"NOT ({self.part.to_sql()})"

    def attributes(self) -> set[str]:
        return self.part.attributes()


def conjuncts(p: Predicate) -> list[Predicate]:
    """The top-level conjuncts of a predicate (a single atom is its own list)."""
    if isinstance(p, TrueP):
        return []
    if isinstance(p, And):
        return list(p.parts)
    return [p]


# --------------------------------------------------------------------------- parser

_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<str>'(?:[^']|'')*'|"(?:[^"]|"")*")
      | (?P<num>-?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)
      | (?P<op><=|>=|<>|!=|==|=|<|>)
      | (?P<punct>[(),])
      | (?P<word>[A-Za-z_][A-Za-z0-9_\-\.]*)
    )""",
    re.VERBOSE,
)


def _tokenize(text: str) -> list[tuple[str, str]]:
    pos, toks = 0, []
    text = text.strip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise SyntaxError(f"cannot tokenize predicate at: {text[pos:]!r}")
        pos = m.end()
        kind = m.lastgroup
        toks.append((kind, m.group(kind)))
    return toks


class _Parser:
    def __init__(self, text: str):
        self.toks = _tokenize(text)
        self.i = 0

    def peek(self, k: int = 0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else (None, None)

    def take(self):
        t = self.peek()
        self.i += 1
        return t

    def kw(self, word: str, k: int = 0) -> bool:
        kind, val = self.peek(k)
        return kind == "word" and val.upper() == word

    def expect_punct(self, p: str):
        kind, val = self.take()
        if kind != "punct" or val != p:
            raise SyntaxError(f"expected {p!r}, got {val!r}")

    def parse(self) -> Predicate:
        if not self.toks:
            return TrueP()
        e = self.expr()
        if self.i != len(self.toks):
            raise SyntaxError(f"unexpected trailing token {self.peek()[1]!r}")
        return e

    def expr(self) -> Predicate:
        parts = [self.term()]
        while self.kw("OR"):
            self.take()
            parts.append(self.term())
        return parts[0] if len(parts) == 1 else Or(parts)

    def term(self) -> Predicate:
        parts = [self.factor()]
        while self.kw("AND"):
            self.take()
            parts.append(self.factor())
        return parts[0] if len(parts) == 1 else And(parts)

    def factor(self) -> Predicate:
        if self.kw("NOT"):
            self.take()
            return Not(self.factor())
        kind, val = self.peek()
        if kind == "punct" and val == "(":
            self.take()
            e = self.expr()
            self.expect_punct(")")
            return e
        if self.kw("TRUE"):
            self.take()
            return TrueP()
        return self.atom()

    def value(self):
        kind, val = self.take()
        if kind == "str":
            q = val[0]
            return val[1:-1].replace(q + q, q)
        if kind == "num":
            f = float(val)
            return int(f) if re.fullmatch(r"-?\d+", val) else f
        if kind == "word":
            return val
        raise SyntaxError(f"expected a value, got {val!r}")

    def atom(self) -> Predicate:
        kind, attr = self.take()
        if kind not in ("word", "str"):
            raise SyntaxError(f"expected an attribute name, got {attr!r}")
        if kind == "str":
            attr = attr[1:-1]
        negate = False
        if self.kw("NOT") and self.kw("IN", 1):
            self.take()
            negate = True
        if self.kw("IN"):
            self.take()
            self.expect_punct("(")
            vals = [self.value()]
            while self.peek() == ("punct", ","):
                self.take()
                vals.append(self.value())
            self.expect_punct(")")
            return Atom(attr, "NOT IN" if negate else "IN", tuple(vals))
        kind, op = self.take()
        if kind != "op":
            raise SyntaxError(f"expected a comparison operator after {attr!r}, got {op!r}")
        op = {"==": "=", "<>": "!="}.get(op, op)
        return Atom(attr, op, self.value())


def parse(text: str | Predicate) -> Predicate:
    """Parse a WHERE-clause string into a :class:`Predicate` (idempotent on predicates)."""
    if isinstance(text, Predicate):
        return text
    return _Parser(text).parse()
