"""Adaptive engine for a critical-thinking learning game.

Two layers, following Chapter 2 of the thesis:

* an estimation layer -- Bayesian Knowledge Tracing (:mod:`ct_adaptive.bkt`);
* a decision layer -- nine transparent adaptation rules (:mod:`ct_adaptive.rules`).

:mod:`ct_adaptive.simulation` runs synthetic learners through the engine so that
its behaviour can be studied before any real classroom data exist.
"""

__version__ = "0.1.0"
