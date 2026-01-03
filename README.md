# private_query_explanations

Reference implementation of the core pseudocode found in `Private_Query_Refinement.pdf`:

- **Algorithm 1**: *Private-Queries-Diff-Top-K-Explanation*
- **Algorithm 2**: *Find-Top-k-Explanations*

The PDF draft contains some placeholders / unspecified subroutines (e.g., exact
view-generation, the exact “one-shot top-τ” primitive, and the full diversity
penalty). This repo implements the algorithms exactly where specified, and uses
standard DP defaults where the draft is underspecified.

### Run the demo

```bash
python3 -m pqr.demo
```

### Use as a library

```python
from pqr.algorithm import generate_simple_predicate_views, private_queries_diff_topk_explanation
from pqr.query import Condition, Op, Query

dataset = [
    {"department": "sales", "country": "US", "gender": "F"},
    {"department": "engineering", "country": "US", "gender": "M"},
]

q1 = Query((Condition("department", Op.EQ, "sales"),))
q2 = Query((Condition("department", Op.EQ, "engineering"),))

predicate_views = generate_simple_predicate_views(dataset, predicate_attrs=["country"])

explanations = private_queries_diff_topk_explanation(
    dataset=dataset,
    q1=q1,
    q2=q2,
    attributes=["gender"],
    predicate_views=predicate_views,
    tau=3,
    k=1,
    epsilon=1.0,
)
print(explanations)
```

