"""
engine/services/products.py

Service layer for product price helpers.

This module is careful to avoid circular imports at module import time:
- model imports are done lazily inside functions.
- functions are defensive: if expected models/fields are absent they return
  sensible defaults and a short 'note' describing what went wrong.

Public functions
- product_starting_price(product_or_pk_or_slug) -> dict
    Returns the lowest (starting) price for a product and some metadata.
- get_product_price_range(product_or_pk_or_slug) -> dict
    Returns min/max/count and an optional list of price entries (summary).

Notes:
- The exact field names used by your product/price models may vary.
  This service attempts a few common conventions and falls back gracefully.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union


def _to_decimal(v, default=Decimal("0.00")) -> Decimal:
    try:
        if v is None:
            return default
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))
    except Exception:
        return default


def _resolve_product(obj: Union[int, str, Any]) -> Tuple[Optional[Any], Optional[str]]:
    """
    Try to resolve a product model instance from:
      - a model instance (returned as-is)
      - a primary key (int)
      - a slug (str)
    Returns (product_instance_or_None, note)
    """
    # Early return if already looks like a model instance (has .__class__ and likely attributes)
    # We can't reliably detect a Django model without importing django, so be permissive:
    if obj is None:
        return None, "no product provided"

    # If the caller passed an instance that looks like a product (has 'id' or 'pk' and 'name'/'title'), return it
    if not isinstance(obj, (int, str)):
        # basic heuristic: has 'pk' or 'id' attribute
        if hasattr(obj, "pk") or hasattr(obj, "id"):
            return obj, "instance_passed"

    # Otherwise attempt to fetch from the DB using common Product model locations
    try:
        # try import the app's Product model
        from products.models import Product  # type: ignore

        if isinstance(obj, int):
            prod = Product.objects.filter(pk=int(obj)).first()
            if prod:
                return prod, "lookup_by_pk"
            return None, f"Product(pk={obj}) not found"
        if isinstance(obj, str):
            # try slug or name
            prod = Product.objects.filter(slug=obj).first() or Product.objects.filter(name__iexact=obj).first()
            if prod:
                return prod, "lookup_by_slug_or_name"
            # try UUID pk style
            try:
                prod = Product.objects.filter(pk=obj).first()
                if prod:
                    return prod, "lookup_by_pk_string"
            except Exception:
                pass
            return None, f"Product(slug/name={obj}) not found"
    except Exception as e:
        # products.models might not be importable here (circular import or different layout)
        return None, f"could not import products.models.Product: {e}"

    return None, "unresolved"


def _collect_price_objects(product) -> Tuple[List[Any], List[str]]:
    """
    Given a product instance, try to discover related price objects.
    Returns (price_objects_list, notes_list).

    Common relationships checked:
      - product.prices.all()
      - product.price_set.all()
      - product.digital_prices.all()
      - product.prices (if it's already a queryset/list)
      - product.base_price / product.price (single-field)
    """
    prices = []
    notes = []

    if product is None:
        notes.append("no product instance given")
        return prices, notes

    # If product has an attribute that's already an iterable of prices, prefer that
    for attr in ("prices", "price_set", "digital_prices", "product_prices"):
        val = getattr(product, attr, None)
        if val is None:
            continue
        try:
            # If it's a manager or queryset
            queryset = val.all() if hasattr(val, "all") else val
            # Convert to list safely
            items = list(queryset)
            if items:
                prices.extend(items)
                notes.append(f"found related prices via product.{attr}")
                # keep scanning to collect all possible variations
        except Exception:
            # maybe val itself is a single price object
            try:
                prices.append(val)
                notes.append(f"found single price object at product.{attr}")
            except Exception:
                pass

    # If no related price objects, try single fields like base_price, price
    if not prices:
        for fld in ("base_price", "price", "starting_price"):
            if hasattr(product, fld):
                try:
                    val = getattr(product, fld)
                    if val is not None:
                        # wrap into a simple dict-like object
                        prices.append({"__price_field__": fld, "value": val})
                        notes.append(f"found {fld} on product")
                except Exception:
                    pass

    if not prices:
        notes.append("no price relations or price fields found on product")

    return prices, notes


def _extract_price_value(price_obj) -> Optional[Decimal]:
    """
    Try to extract a numeric price value from a price object. Returns Decimal or None.
    Common fields checked:
      - price_per_sheet, price, amount, unit_price, value, rate, price_per_unit, price_cents (converted)
      - for dict-like wrappers created above: ['value']
    """
    if price_obj is None:
        return None

    # If it's a dict-like we created above
    if isinstance(price_obj, dict):
        if "value" in price_obj:
            return _to_decimal(price_obj.get("value"))
        # check other keys
        for k in ("price_per_sheet", "price", "amount", "unit_price", "value", "rate"):
            if k in price_obj:
                return _to_decimal(price_obj.get(k))
        return None

    # Otherwise try common attributes on Django model instance
    for attr in (
        "price_per_sheet",
        "price",
        "amount",
        "unit_price",
        "value",
        "rate",
        "rate_per_1000",
        "price_per_1000",
    ):
        if hasattr(price_obj, attr):
            try:
                v = getattr(price_obj, attr)
                # if it's a callable property, call it
                if callable(v):
                    try:
                        v = v()
                    except Exception:
                        pass
                return _to_decimal(v)
            except Exception:
                continue

    # As a last resort, try numeric repr of the object (not recommended)
    try:
        return _to_decimal(price_obj)
    except Exception:
        return None


def product_starting_price(product_or_pk_or_slug: Union[int, str, Any]) -> Dict[str, Any]:
    """
    Return the starting (lowest) price information for a product.

    Returns dict:
      {
        "product": product_instance_or_None,
        "product_note": str,
        "starting_price": Decimal,
        "starting_price_source": str,   # e.g. "product.base_price" or "price_obj.id:123"
        "price_count": int,
        "notes": [ ... ],
      }

    This function will not raise on missing models; it returns helpful notes instead.
    """
    result = {
        "product": None,
        "product_note": None,
        "starting_price": Decimal("0.00"),
        "starting_price_source": None,
        "price_count": 0,
        "notes": [],
    }

    product, pnote = _resolve_product(product_or_pk_or_slug)
    result["product"] = product
    result["product_note"] = pnote

    if product is None:
        result["notes"].append(f"product resolution: {pnote}")
        return result

    prices, discovered_notes = _collect_price_objects(product)
    result["notes"].extend(discovered_notes)

    # Extract numeric values and rank them
    numeric_prices = []
    for p in prices:
        val = _extract_price_value(p)
        if val is not None:
            numeric_prices.append((val, p))

    if not numeric_prices:
        result["notes"].append("no numeric price values could be extracted")
        return result

    # Choose minimum positive price (exclude zeros unless all are zeros)
    numeric_sorted = sorted(numeric_prices, key=lambda x: x[0])
    # prefer >0
    positive = [t for t in numeric_sorted if t[0] > 0]
    chosen = positive[0] if positive else numeric_sorted[0]
    chosen_val, chosen_obj = chosen

    result["starting_price"] = chosen_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    result["starting_price_source"] = getattr(chosen_obj, "pk", None) or getattr(chosen_obj, "__price_field__", None) or str(type(chosen_obj))
    result["price_count"] = len(numeric_prices)
    result["notes"].append(f"selected starting price {result['starting_price']} from {result['starting_price_source']}")

    return result


def get_product_price_range(product_or_pk_or_slug: Union[int, str, Any], include_details: bool = False) -> Dict[str, Any]:
    """
    Return the min/max/median-ish range for a product's prices.

    Returns:
      {
        "product": product_instance_or_None,
        "product_note": str,
        "min_price": Decimal or None,
        "max_price": Decimal or None,
        "count": int,
        "prices": [ Decimal, ... ]  # optional when include_details=True
        "notes": [...]
      }
    """
    out = {
        "product": None,
        "product_note": None,
        "min_price": None,
        "max_price": None,
        "count": 0,
        "prices": [] if include_details else None,
        "notes": [],
    }

    product, pnote = _resolve_product(product_or_pk_or_slug)
    out["product"] = product
    out["product_note"] = pnote

    if product is None:
        out["notes"].append(f"product resolution: {pnote}")
        return out

    prices, notes = _collect_price_objects(product)
    out["notes"].extend(notes)

    numeric_values: List[Decimal] = []
    for p in prices:
        v = _extract_price_value(p)
        if v is not None:
            numeric_values.append(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    if not numeric_values:
        out["notes"].append("no numeric price values found")
        return out

    numeric_values = sorted(numeric_values)
    out["min_price"] = numeric_values[0]
    out["max_price"] = numeric_values[-1]
    out["count"] = len(numeric_values)
    if include_details:
        out["prices"] = numeric_values

    return out
