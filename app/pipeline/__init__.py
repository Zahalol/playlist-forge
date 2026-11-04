"""Pure data pipeline: classify -> parse -> enrich -> weights -> profile -> recommend -> playlist -> export.

Every module here takes plain data in and returns plain data out. No web, no database, no network
(except enrich.py, whose clients are injected so tests can mock them).
"""
