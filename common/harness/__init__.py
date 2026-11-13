"""The central harness (D005, D017).

One process owns the simulation clock, starts every module as a
process of its own, and passes each module's outputs to the modules
that read them, one tick at a time. ``core.Harness`` is the tick loop;
``README.md`` in this folder says how the parts fit and how a module
joins. R and G numbers in this package refer to
``documents/system-integration-design.md``.

``ctc_edges`` and ``track_model_edges`` predate the process model;
``track_model_edges`` still maps through the catalog in
``common/interfaces.py``, which is superseded (R11).
"""
