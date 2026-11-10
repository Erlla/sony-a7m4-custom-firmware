"""Runtime version shared by the UI, workflow, integrity checks and launchers.

The builder also requires this literal to match dependencies.json. A mismatched
published package remains rejected; this is not a legacy-version alias.
"""
VERSION = '1.01'
