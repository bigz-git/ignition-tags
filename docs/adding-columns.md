# Adding a New Tag Property Column

The tool is designed so that adding a new Ignition tag property requires **one line in `columns.py`** — no changes to `core.py` or `cli.py`.

## How it works

`columns.py` contains dicts that map normalized Excel column names (lowercase, stripped) to Ignition JSON keys. The processing loops in `core.py` iterate over these dicts automatically, so any entry you add is picked up without further changes.

## Which dict to add to

| Dict | Use for |
|---|---|
| `TAG_SCALAR_FIELDS` | Free-text or string fields that copy 1-to-1 into the tag JSON |
| `TAG_ENG_FIELDS` | Numeric engineering-range fields (`engLow`, `engHigh` style) |
| `TAG_ALARM_FIELDS` | Fields that go inside the `alarms[0]` sub-object |
| `UDT_TAG_FIELDS` | Fields on UDT tag rows in the `UDT_LIST` sheet |

## Example: adding `tagGroup`

Ignition's JSON key for tag group is `tagGroup`. To support a `taggroup` Excel column:

Open [ignition_tags/columns.py](../ignition_tags/columns.py) and add one line to `TAG_SCALAR_FIELDS`:

```python
TAG_SCALAR_FIELDS = {
    "documentation": "documentation",
    "tooltip":       "tooltip",
    "engunit":       "engUnit",
    "taggroup":      "tagGroup",   # <-- add this line
}
```

Then add a `taggroup` column to your `DEVICE_LIST` sheet. That's it.

## Example: adding `deadband`

Ignition's `deadband` property is numeric. Add it to `TAG_ENG_FIELDS` so it gets the same float-coercion treatment as `engLow`/`engHigh`:

```python
TAG_ENG_FIELDS = {
    "englow":    "engLow",
    "enghigh":   "engHigh",
    "deadband":  "deadband",   # <-- add this line
}
```

## Limitations

- This approach covers **scalar fields only** — properties with a simple value (string, number, boolean).
- Fields that require a nested sub-object (like `alarms`, or future nested structures) need logic changes in `core.py` and are not a one-line addition.
- Boolean fields (like `readOnly`) have special handling in `core.py` and are not covered by the generic scalar loop. Ask before adding one.
