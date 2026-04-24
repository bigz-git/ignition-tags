"""
ignition_tags — Ignition SCADA tag import/export library.

Public API (intended for use by a GUI layer or scripts):

    from ignition_tags import build_tag_provider, build_udt_types, flatten_tags

CLI:
    python -m ignition_tags --help
"""

from .core import build_tag_provider, build_udt_types, flatten_tags, flatten_udt_types

__all__ = ["build_tag_provider", "build_udt_types", "flatten_tags", "flatten_udt_types"]
