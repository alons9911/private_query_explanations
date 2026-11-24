"""Counterexamples to the HD sensitivity bound (Prop. 4.2) in the CQA setting.

HD is computed exactly as in Definition 4.1 of the paper:
    HD = sum_V |H_Q(p(D)),A(V) - H_Q'(p(D)),A(V)| / H_p(D),A(V)
with p = true. Q is the raw query, Q' its certain answers (tuples in every repair).
Prop. 4.2 claims |HD(D) - HD(D')| <= 1 for neighbouring D, D'.

Run: python3 scripts/sensitivity_counterexamples.py
"""


def hd(D, Q, Qp, A, dom):
    QD, QpD = Q(D), Qp(D)
    s = 0.0
    for v in dom:
        n = sum(t[A] == v for t in D)
        if n:
            s += abs(sum(t[A] == v for t in QD) - sum(t[A] == v for t in QpD)) / n
    return s


def certain_fd(D, X, Y):
    """Tuples present in every repair under the FD X -> Y."""
    return [t for t in D if all(u[Y] == t[Y] for u in D if u[X] == t[X])]


def certain_pk(D, key):
    """Tuples present in every repair under a primary key: singleton blocks."""
    return [t for t in D if sum(u[key] == t[key] for u in D) == 1]


Q = lambda D: list(D)


def check(name, D, D2, Qp, A, dom):
    a, b = hd(D, Q, Qp, A, dom), hd(D2, Q, Qp, A, dom)
    print(f"{name:<28} HD(D)={a:<5} HD(D')={b:<5} |diff|={abs(a - b):<5} claimed<=1")


if __name__ == "__main__":
    # Example 1: FD Dept -> City; one tuple with a conflicting City empties Q'.
    D = [dict(name=f"e{i}", dept="RnD", city="Haifa", g=g) for i, g in enumerate("FFMM")]
    D2 = D + [dict(name="t", dept="RnD", city="TLV", g="F")]
    check("FD, 2 buckets", D, D2, lambda D: certain_fd(D, "dept", "city"), "g", "FM")

    # Example 2: the same with 10 buckets -> the change equals the full range of HD.
    dom = [str(i) for i in range(10)]
    D = [dict(dept="RnD", city="Haifa", g=str(i % 10)) for i in range(1000)]
    D2 = D + [dict(dept="RnD", city="TLV", g="0")]
    check("FD, 10 buckets", D, D2, lambda D: certain_fd(D, "dept", "city"), "g", dom)

    # Example 3: primary key on Name; the change is bounded, but by 2, not 1.
    D = [dict(name="Dana", g="F")]
    D2 = D + [dict(name="Dana", g="M")]
    check("Primary key", D, D2, lambda D: certain_pk(D, "name"), "g", "FM")
