"""
engine/services/costs.py

Cost service adapted to your pricing model (DigitalPrintPrice).
- Prefers direct deliverable overrides when present.
- If price_obj is None, attempts to auto-resolve a DigitalPrintPrice using
  deliverable.inner_machine and deliverable.inner_material.paper_type (lazy import).
- Booklets default to double-sided; otherwise default to single-sided.
- Defensive: returns helpful warnings when data is missing.
"""
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Dict, Optional
from types import SimpleNamespace

# imposition helpers (these are safe to import)
from engine.services.impositions import items_per_sheet, sheets_needed, booklet_imposition

getcontext().prec = 12


def _to_decimal(v, default=Decimal("0.00")) -> Decimal:
    if isinstance(v, Decimal):
        return v
    try:
        if v is None:
            return default
        return Decimal(str(v))
    except Exception:
        return default


def _format_currency(amount: Decimal, currency: str = "KES") -> str:
    try:
        a = (amount or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{currency} {a:,}"
    except Exception:
        return f"{currency} 0.00"


def _is_booklet(deliverable: Any) -> bool:
    """Return True if the deliverable is a booklet (saddle-stitched / total_pages)."""
    return bool(getattr(deliverable, "saddle_stitched", False)) or bool(getattr(deliverable, "total_pages", None))


def _get_sheet_sidedness(deliverable: Any) -> str:
    """
    Determine sidedness for pricing decision.

    Priority:
      1) deliverable.duplex (bool) -> 'double' if True else 'single'
      2) deliverable.inner_sidedness or deliverable.sidedness (text) -> detect 'double' / 'duplex' / '2'
      3) if booklet -> 'double'
      4) default -> 'single'
    """
    duplex = getattr(deliverable, "duplex", None)
    if duplex is not None:
        return "double" if bool(duplex) else "single"

    sided = getattr(deliverable, "inner_sidedness", None)
    if not sided:
        sided = getattr(deliverable, "sidedness", None)
    if sided:
        s = str(sided).lower()
        if "double" in s or "duplex" in s or "two" in s or "2" in s:
            return "double"
        return "single"

    # If it's a booklet prefer duplex
    if _is_booklet(deliverable):
        return "double"

    # default single-sided
    return "single"


def _auto_find_price_obj(deliverable: Any) -> Optional[Any]:
    """
    Try to find a DigitalPrintPrice for this deliverable.

    Matching priority:
      1) machine + price.size == material.size (strongest: price explicitly for that production sheet)
      2) machine + paper_type (paper stock match)
      3) machine only (last resort)

    This is lazy and defensive; returns None if pricing app is unavailable.
    """
    # If deliverable already has an explicit print_price, use it
    existing = getattr(deliverable, "print_price", None)
    if existing is not None:
        return existing

    try:
        from pricing.models import DigitalPrintPrice  # lazy import
    except Exception:
        return None

    machine = getattr(deliverable, "inner_machine", None)
    material = getattr(deliverable, "inner_material", None)

    qs = DigitalPrintPrice.objects.all()
    try:
        # 1) If deliverable has an inner_material with a .size, match price.size exactly
        if machine is not None and material is not None:
            mat_size = getattr(material, "size", None)
            if mat_size is not None:
                found = qs.filter(machine=machine, size=mat_size).first()
                if found:
                    return found

        # 2) If deliverable has an inner_material that references a PaperType, match by paper_type
        if machine is not None and material is not None:
            # try to read .paper_type (works if inner_material is a material wrapper)
            paper_type = getattr(material, "paper_type", None)
            if paper_type is None:
                # maybe inner_material *is* actually a PaperType instance
                # detect by presence of 'name' and absence of 'paper_type'
                if getattr(material, "name", None) and not getattr(material, "paper_type", None):
                    paper_type = material
            if paper_type is not None:
                found = qs.filter(machine=machine, paper_type=paper_type).first()
                if found:
                    return found

        # 3) Fallback: any price row for the machine (first available)
        if machine is not None:
            found = qs.filter(machine=machine).first()
            if found:
                return found

    except Exception:
        # DB error or attribute problems -> give up gracefully
        return None

    return None


def _build_price_proxy_from(deliverable: Any, price_obj: Optional[Any]) -> SimpleNamespace:
    """
    Build a price proxy with Decimal-normalised fields.

    Sources (priority):
      1) explicit deliverable fields (single_side_price, double_side_price, price_per_sheet, unit_price, minimum_charge, currency, etc.)
      2) passed price_obj (DigitalPrintPrice instance)
      3) nothing -> sensible zeros/defaults
    """
    vals = {}

    # candidate keys to look for on deliverable or price_obj
    keys = (
        "price_per_sheet",
        "single_side_price",
        "double_side_price",
        "rate_per_1000",
        "setup_cost",
        "makeready_cost",
        "waste_percent",
        "finishing_cost_per_sheet",
        "cover_price_per_sheet",
        "unit_price",
        "minimum_charge",
        "currency",
    )

    # collect from deliverable first
    for k in keys:
        if hasattr(deliverable, k):
            vals[k] = getattr(deliverable, k)

    # collect from price_obj next if not present or falsy
    if price_obj is not None:
        for k in keys:
            if k not in vals or vals.get(k) in (None, "", 0):
                if hasattr(price_obj, k):
                    vals[k] = getattr(price_obj, k)

        # your pricing model uses single_side_price / double_side_price
        # also accept 'size' field but not required here

    # Decide sidedness and pick base price_per_sheet
    sided = _get_sheet_sidedness(deliverable)
    base_pps: Optional[Decimal] = None

    # If explicit price_per_sheet provided, use it
    if vals.get("price_per_sheet") not in (None, "", 0):
        base_pps = _to_decimal(vals.get("price_per_sheet"))
    else:
        if sided == "double":
            if vals.get("double_side_price") not in (None, "", 0):
                base_pps = _to_decimal(vals.get("double_side_price"))
            elif vals.get("single_side_price") not in (None, "", 0):
                # assume single_side_price is per sheet single; double may be equivalent to same field in your model.
                base_pps = _to_decimal(vals.get("single_side_price"))
        else:  # single
            if vals.get("single_side_price") not in (None, "", 0):
                base_pps = _to_decimal(vals.get("single_side_price"))
            elif vals.get("double_side_price") not in (None, "", 0):
                # if only double available and job is single, prefer using double as-is (you can change policy)
                base_pps = _to_decimal(vals.get("double_side_price"))

    # fallback to rate_per_1000
    if (base_pps is None or base_pps == Decimal("0")) and vals.get("rate_per_1000") not in (None, "", 0):
        base_pps = (_to_decimal(vals.get("rate_per_1000")) / Decimal("1000")).quantize(Decimal("0.0001"))

    proxy = {
        "price_per_sheet": base_pps or Decimal("0.00"),
        "rate_per_1000": _to_decimal(vals.get("rate_per_1000", None)),
        "setup_cost": _to_decimal(vals.get("setup_cost", None)),
        "makeready_cost": _to_decimal(vals.get("makeready_cost", None)),
        "waste_percent": _to_decimal(vals.get("waste_percent", None)),
        "finishing_cost_per_sheet": _to_decimal(vals.get("finishing_cost_per_sheet", None)),
        "cover_price_per_sheet": _to_decimal(vals.get("cover_price_per_sheet", None)),
        "unit_price": _to_decimal(vals.get("unit_price", None), None),
        "minimum_charge": _to_decimal(vals.get("minimum_charge", None), Decimal("0.00")),
        "currency": vals.get("currency") or (getattr(price_obj, "currency", None) if price_obj is not None else "KES"),
    }
    return SimpleNamespace(**proxy)


def compute_sheets_for_deliverable(deliverable: Any, price_obj: Optional[Any] = None) -> Dict[str, Any]:
    """
    Return imposition/sheet counts for the deliverable.

    If price_obj is None attempts to auto-resolve a price object (but does not fail if missing).
    """
    # if no price_obj provided, attempt to auto-find one
    if price_obj is None:
        price_obj = _auto_find_price_obj(deliverable)

    result: Dict[str, Any] = {}
    qty = getattr(deliverable, "quantity", None)
    result["qty"] = qty

    final_size = getattr(deliverable, "size", None)
    final_w = getattr(final_size, "width_mm", None) if final_size else None
    final_h = getattr(final_size, "height_mm", None) if final_size else None

    # production sheet size (prefer price_obj.size)
    sheet_w = None
    sheet_h = None
    sheet_name = None
    if price_obj is not None and getattr(price_obj, "size", None) is not None:
        s = getattr(price_obj, "size")
        sheet_w = getattr(s, "width_mm", None)
        sheet_h = getattr(s, "height_mm", None)
        sheet_name = getattr(s, "name", None)

    if sheet_w is None and getattr(deliverable, "inner_material", None) is not None:
        try:
            msize = getattr(deliverable.inner_material, "size", None)
            if msize:
                sheet_w = getattr(msize, "width_mm", None)
                sheet_h = getattr(msize, "height_mm", None)
                sheet_name = getattr(msize, "name", None)
        except Exception:
            pass

    if sheet_w is None and getattr(deliverable, "inner_machine", None) is not None:
        try:
            machine = deliverable.inner_machine
            ss = getattr(machine, "supported_sizes", None)
            if ss is not None:
                first = ss.first()
                if first:
                    sheet_w = getattr(first, "width_mm", None)
                    sheet_h = getattr(first, "height_mm", None)
                    sheet_name = getattr(first, "name", None)
        except Exception:
            pass

    # Booklet branch
    is_book = _is_booklet(deliverable)
    result["is_booklet"] = is_book

    if is_book:
        total_pages = int(getattr(deliverable, "total_pages", 0) or 0)
        if total_pages <= 0:
            return {
                "pages_per_physical_sheet": None,
                "inner_sheets": 0,
                "cover_sheets": 0,
                "total_physical_sheets": 0,
                "imposition": {},
                "warnings": ["booklet detected but total_pages missing or zero"],
            }

        cover_separate = bool(getattr(deliverable, "cover_separate", True))

        cover_size_obj = None
        if price_obj is not None and getattr(price_obj, "cover_size", None) is not None:
            cover_size_obj = getattr(price_obj, "cover_size")
        if getattr(deliverable, "cover_sheet_size", None):
            cover_size_obj = deliverable.cover_sheet_size

        cover_w = getattr(cover_size_obj, "width_mm", None) if cover_size_obj else None
        cover_h = getattr(cover_size_obj, "height_mm", None) if cover_size_obj else None

        imposition = booklet_imposition(
            total_pages=total_pages,
            final_page_w_mm=final_w,
            final_page_h_mm=final_h,
            sheet_w_mm=sheet_w,
            sheet_h_mm=sheet_h,
            bleed_mm=getattr(deliverable, "bleed_mm", 3),
            gutter_mm=getattr(deliverable, "gutter_mm", 5),
            margin_mm=getattr(deliverable, "gripper_mm", 10),
            duplex=True,  # booklets are imposed duplex
            enforce_signature_multiple=int(getattr(deliverable, "signature_multiple", 4)),
            cover_separate=cover_separate,
            cover_sheet_w_mm=cover_w,
            cover_sheet_h_mm=cover_h,
            cover_bleed_mm=getattr(deliverable, "cover_bleed_mm", None),
            cover_gutter_mm=getattr(deliverable, "cover_gutter_mm", None),
            cover_margin_mm=getattr(deliverable, "cover_gripper_mm", None),
        )

        result["imposition"] = imposition
        result["pages_per_physical_sheet"] = imposition.get("pages_per_physical_sheet")
        result["inner_sheets"] = int(imposition.get("inner_sheets", 0) or 0)
        result["cover_sheets"] = int(imposition.get("cover_sheets", 0) or 0)
        result["total_physical_sheets"] = int(imposition.get("total_physical_sheets", 0) or (result["inner_sheets"] + result["cover_sheets"]))
        return result

    # Non-booklet flow
    if sheet_w is None or sheet_h is None:
        return {
            "items_per_sheet": 0,
            "inner_sheets": 0,
            "cover_sheets": 0,
            "total_physical_sheets": 0,
            "imposition": {},
            "warnings": ["could not resolve production sheet size"],
        }

    items = items_per_sheet(
        sheet_w_mm=sheet_w,
        sheet_h_mm=sheet_h,
        item_w_mm=final_w,
        item_h_mm=final_h,
        bleed_mm=getattr(deliverable, "bleed_mm", 3),
        gutter_mm=getattr(deliverable, "gutter_mm", 5),
        margin_mm=getattr(deliverable, "gripper_mm", 10),
    )

    result["items_per_sheet"] = int(items or 0)
    if qty is None:
        result["inner_sheets"] = 0
        result["cover_sheets"] = 0
        result["total_physical_sheets"] = 0
        result["imposition"] = {"items_per_sheet": items}
        return result

    sheets = sheets_needed(qty, items)
    result["inner_sheets"] = int(sheets)
    result["cover_sheets"] = 0
    result["total_physical_sheets"] = int(sheets)
    result["imposition"] = {"items_per_sheet": items}
    return result


def compute_print_run_cost(sheet_count: int, price_proxy: Any, *, is_cover: bool = False, extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Compute cost for a run given a price proxy (SimpleNamespace-like).
    """
    extras = extras or {}
    warnings = []
    sc = int(sheet_count or 0)
    if sc <= 0:
        return {
            "sheet_count": 0,
            "price_per_sheet": Decimal("0.00"),
            "setup_cost": Decimal("0.00"),
            "makeready_cost": Decimal("0.00"),
            "waste_sheets": 0,
            "waste_cost": Decimal("0.00"),
            "running_cost": Decimal("0.00"),
            "finishing_cost": Decimal("0.00"),
            "extras_cost": Decimal("0.00"),
            "total_run_cost": Decimal("0.00"),
            "warnings": ["zero sheet_count"],
        }

    pps = _to_decimal(getattr(price_proxy, "price_per_sheet", None), Decimal("0.00"))
    rate_per_1000 = _to_decimal(getattr(price_proxy, "rate_per_1000", None), Decimal("0.00"))
    setup_cost = _to_decimal(getattr(price_proxy, "setup_cost", None), Decimal("0.00"))
    makeready_cost = _to_decimal(getattr(price_proxy, "makeready_cost", None), Decimal("0.00"))
    waste_percent = _to_decimal(getattr(price_proxy, "waste_percent", None), Decimal("0.00"))
    finishing = _to_decimal(getattr(price_proxy, "finishing_cost_per_sheet", None), Decimal("0.00"))

    if pps == Decimal("0.00") and rate_per_1000 > 0:
        pps = (rate_per_1000 / Decimal("1000")).quantize(Decimal("0.0001"))

    if pps == Decimal("0.00"):
        warnings.append("price_per_sheet is zero")

    waste_sheets = int((Decimal(sc) * (waste_percent / Decimal("100"))).to_integral_value(rounding=ROUND_HALF_UP)) if waste_percent > 0 else 0
    waste_cost = (Decimal(waste_sheets) * pps).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    running_cost = (Decimal(sc) * pps).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    finishing_cost = (Decimal(sc) * finishing).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    extras_cost = Decimal("0.00")
    for k, v in extras.items():
        dv = _to_decimal(v, Decimal("0.00"))
        if k.endswith("_per_sheet"):
            extras_cost += (Decimal(sc) * dv)
        elif k.endswith("_flat"):
            extras_cost += dv
        else:
            extras_cost += dv

    total_run = (running_cost + waste_cost + setup_cost + makeready_cost + finishing_cost + extras_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "sheet_count": sc,
        "price_per_sheet": pps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "setup_cost": setup_cost.quantize(Decimal("0.01")),
        "makeready_cost": makeready_cost.quantize(Decimal("0.01")),
        "waste_percent": waste_percent,
        "waste_sheets": waste_sheets,
        "waste_cost": waste_cost,
        "running_cost": running_cost,
        "finishing_cost": finishing_cost,
        "extras_cost": extras_cost.quantize(Decimal("0.01")),
        "total_run_cost": total_run,
        "warnings": warnings,
    }


def compute_total_cost(deliverable: Any, price_obj: Optional[Any] = None, *, cover_price_obj: Optional[Any] = None, extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Top-level cost computation.

    If price_obj is None, attempts to auto-find one from pricing models.
    """
    extras = extras or {}
    warnings = []

    # if no explicit price_obj, try to auto-resolve from pricing table
    if price_obj is None:
        price_obj = _auto_find_price_obj(deliverable)

    price_proxy = _build_price_proxy_from(deliverable, price_obj)
    cover_proxy = _build_price_proxy_from(deliverable, cover_price_obj if cover_price_obj is not None else price_obj)

    sheets = compute_sheets_for_deliverable(deliverable, price_obj=price_obj)
    inner_sheets = int(sheets.get("inner_sheets", 0) or 0)
    cover_sheets = int(sheets.get("cover_sheets", 0) or 0)

    # If we have only unit_price, convert to price_per_sheet if items per sheet known
    if getattr(price_proxy, "price_per_sheet", Decimal("0.00")) == Decimal("0.00") and getattr(price_proxy, "unit_price", None) is not None:
        imposition = sheets.get("imposition", {}) or {}
        items_on_sheet = imposition.get("pages_per_physical_sheet") or imposition.get("items_per_sheet")
        try:
            ips = int(items_on_sheet) if items_on_sheet else None
            if ips and ips > 0:
                price_proxy.price_per_sheet = (_to_decimal(price_proxy.unit_price) * Decimal(ips)).quantize(Decimal("0.01"))
        except Exception:
            pass

    inner_run = compute_print_run_cost(inner_sheets, price_proxy, is_cover=False, extras=extras)
    warnings.extend(inner_run.get("warnings", []) or [])

    cover_run = None
    if cover_sheets > 0:
        if getattr(cover_proxy, "price_per_sheet", Decimal("0.00")) == Decimal("0.00") and getattr(price_proxy, "price_per_sheet", Decimal("0.00")) > 0:
            cover_proxy.price_per_sheet = getattr(price_proxy, "price_per_sheet")
        cover_run = compute_print_run_cost(cover_sheets, cover_proxy, is_cover=True, extras=extras)
        warnings.extend(cover_run.get("warnings", []) or [])

    total_cost = inner_run.get("total_run_cost", Decimal("0.00")) or Decimal("0.00")
    if cover_run:
        total_cost += cover_run.get("total_run_cost", Decimal("0.00")) or Decimal("0.00")

    # Respect minimum charge
    min_charge = _to_decimal(getattr(price_proxy, "minimum_charge", None), Decimal("0.00"))
    if min_charge > Decimal("0.00") and total_cost < min_charge:
        warnings.append(f"Applied minimum charge: {min_charge}")
        total_cost = min_charge

    currency = getattr(price_proxy, "currency", "KES") or "KES"
    total_cost = total_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "sheets": {
            "inner_sheets": inner_sheets,
            "cover_sheets": cover_sheets,
            "total_physical_sheets": int((inner_sheets or 0) + (cover_sheets or 0)),
            "imposition": sheets.get("imposition", {}),
        },
        "runs": {"inner": inner_run, "cover": cover_run},
        "total_cost": total_cost,
        "total_cost_formatted": _format_currency(total_cost, currency=currency),
        "warnings": warnings,
    }
