"""
ignition_tags — Ignition SCADA tag import/export library.

Public API (intended for use by a GUI layer or scripts):

    from ignition_tags import build_tag_provider, build_udt_types, flatten_tags

CLI:
    python -m ignition_tags --help
"""

__version__ = "0.1.0"

from .core import build_tag_provider, build_udt_instances, build_udt_types, flatten_tags, flatten_udt_types, split_device_list

__all__ = ["build_tag_provider", "build_udt_instances", "build_udt_types", "flatten_tags", "flatten_udt_types", "split_device_list"]
