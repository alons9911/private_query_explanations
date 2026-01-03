"""
Private Query Refinement (PQR) – reference implementation.

This repository contains a small, self-contained implementation of the core
algorithms described in `Private_Query_Refinement.pdf`:

- Algorithm 1: Private-Queries-Diff-Top-K-Explanation
- Algorithm 2: Find-Top-k-Explanations

The paper draft is incomplete in places (some subroutines are referenced but not
fully specified). This implementation follows the published pseudocode and
definitions that do appear in the PDF, and provides sensible, clearly-marked
defaults for the unspecified pieces (e.g., view generation and one-shot top-τ).
"""

from .algorithm import private_queries_diff_topk_explanation

__all__ = ["private_queries_diff_topk_explanation"]

