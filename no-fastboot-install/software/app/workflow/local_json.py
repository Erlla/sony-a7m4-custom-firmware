"""Shared local state publication; never retry a camera operation here."""
from state_io import atomic_json as atomic, io_path
