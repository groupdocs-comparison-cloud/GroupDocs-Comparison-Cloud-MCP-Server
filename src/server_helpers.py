from datetime import date, datetime
import base64
import binascii


def obj_to_model_kwargs(item, model_cls):
    """
    Convert `item` (dict or object) to kwargs suitable for `model_cls`.
    Performs basic coercions (datetime -> ISO string, int, bool).
    """
    field_map = getattr(model_cls, "model_fields", None) or getattr(model_cls, "__fields__", {})
    names = list(field_map.keys())

    kwargs = {}
    for n in names:
        val = item.get(n) if isinstance(item, dict) else getattr(item, n, None)

        finfo = field_map.get(n)
        annotation = getattr(finfo, "annotation", None) or getattr(finfo, "outer_type_", None)
        ann_str = str(annotation).lower() if annotation is not None else ""

        if isinstance(val, (datetime, date)):
            if "str" in ann_str:
                val = val.isoformat()
        elif val is not None:
            if "int" in ann_str:
                try:
                    val = int(val)
                except Exception:
                    pass
            elif "bool" in ann_str:
                val = bool(val)

        kwargs[n] = val

    return kwargs


def decode_base64_bytes(data: bytes) -> bytes:
    try:
        txt = data.decode("ascii")
    except UnicodeDecodeError:
        return data

    compact = "".join(txt.split())
    if not compact:
        return data
    if len(compact) % 4 != 0:
        return data
    if not all(c.isalnum() or c in "+/=" for c in compact):
        return data

    try:
        return base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError):
        return data


def json_safe_metadata(obj):
    """Recursively convert dict/list values so results are JSON-friendly (e.g. datetime -> ISO)."""
    if isinstance(obj, dict):
        return {k: json_safe_metadata(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe_metadata(x) for x in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj
