"""
engine/services/costs.py

Simplified cost service that assumes imposition/sheet counts are
already available on the JobDeliverable (preferred).

Behavior:
- Prefer deliverable-provided price fields and imposition/sheet counts.
- If price_obj (DigitalPrintPrice) not provided, auto-find one using machine + material.
- Sidedness is read from deliverable.sidedness (simple).
- Returns structured breakdown and formatted total string.
"""
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Dict, Optional
from types import SimpleNamespace

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
        # insert thousands separator
        return f"{currency} {a:,}"
    except Exception:
        return f"{currency} 0.00"


# ---------- Simple sidedness helper ----------
def _get_sheet_sidedness(deliverable: Any) -> str:
    """
    Read sidedness from deliverable.sidedness.
    Return 'single' or 'double'. Default 'single'.
    Accepts simple codes like 'S'/'D' or full words.
    """
    sided = getattr(deliverable, "sidedness", None)
    if not sided:
        return "single"
    s = str(sided).lower()
    if s in ("d", "double", "duplex", "2", "two"):
        return "double"
    return "single"


# ---------- Auto-find price row (simple, prioritized) ----------
def _auto_find_price_obj(deliverable: Any) -> Optional[Any]:
    """
    Find a DigitalPrintPrice for the deliverable.

    Priority:
      1) machine + price.size == material.size
      2) machine + paper_type
      3) any price for the machine
    Returns None if not found or pricing app not available.
    """
    existing = getattr(deliverable, "print_price", None)
    if existing is not None:
        return existing

    try:
        from pricing.models import DigitalPrintPrice  # lazy import
    except Exception:
        return None

    machine = getattr(deliverable, "inner_machine", None)
    material = getattr(deliverable, "inner_material", None)
    if machine is None:
        return None

    qs = DigitalPrintPrice.objects.filter(machine=machine)

    # 1) match by material.size -> price.size
    mat_size = getattr(material, "size", None)
    if mat_size is not None:
        found = qs.filter(size=mat_size).first()
        if found:
            return found

    # 2) match by paper_type
    paper_type = getattr(material, "paper_type", None)
    if paper_type is None:
        # maybe inner_material itself is a PaperType
        if material is not None and getattr(material, "name", None) and not getattr(material, "paper_type", None):
            paper_type = material
    if paper_type is not None:
        found = qs.filter(paper_type=paper_type).first()
        if found:
            return found

    # 3) fallback to any price for machine
    return qs.first()


# ---------- Price proxy builder ----------
def _build_price_proxy_from(deliverable: Any, price_obj: Optional[Any]) -> SimpleNamespace:
    """
    Build a small SimpleNamespace with normalized Decimal fields we use:
      - price_per_sheet
      - setup_cost
      - makeready_cost
      - waste_percent
      - finishing_cost_per_sheet
      - minimum_charge
      - currency

    Priority: deliverable attributes override price_obj values.
    """
    # keys to look for
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

    vals = {}
    for k in keys:
        if hasattr(deliverable, k):
            vals[k] = getattr(deliverable, k)

    if price_obj is not None:
        for k in keys:
            if k not in vals or vals.get(k) in (None, "", 0):
                if hasattr(price_obj, k):
                    vals[k] = getattr(price_obj, k)

    # Choose base price_per_sheet from sidedness-aware fields
    sided = _get_sheet_sidedness(deliverable)
    base_pps: Optional[Decimal] = None

    # direct explicit price_per_sheet wins
    if vals.get("price_per_sheet") not in (None, "", 0):
        base_pps = _to_decimal(vals.get("price_per_sheet"))
    else:
        if sided == "double":
            if vals.get("double_side_price") not in (None, "", 0):
                base_pps = _to_decimal(vals.get("double_side_price"))
            elif vals.get("single_side_price") not in (None, "", 0):
                base_pps = _to_decimal(vals.get("single_side_price"))
        else:  # single
            if vals.get("single_side_price") not in (None, "", 0):
                base_pps = _to_decimal(vals.get("single_side_price"))
            elif vals.get("double_side_price") not in (None, "", 0):
                base_pps = _to_decimal(vals.get("double_side_price"))

    # fallback: rate_per_1000 / 1000
    if (base_pps is None or base_pps == Decimal("0")) and vals.get("rate_per_1000") not in (None, "", 0):
        base_pps = (_to_decimal(vals.get("rate_per_1000")) / Decimal("1000")).quantize(Decimal("0.0001"))

    proxy = {
        "price_per_sheet": base_pps or Decimal("0.00"),
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


# ---------- Read sheet counts from deliverable ----------
def _get_sheet_counts_from_deliverable(deliverable: Any) -> Dict[str, int]:
    """
    Prefer already-calculated imposition/sheet data on the deliverable.

    Expected places (checked in order):
      - deliverable.imposition (dict) with keys 'inner_sheets' and 'cover_sheets' or 'total_physical_sheets'
      - deliverable.inner_sheets, deliverable.cover_sheets, deliverable.total_physical_sheets attributes
      - deliverable.sheets or deliverable.sheet_count (fallback)
    Returns dict {'inner_sheets': int, 'cover_sheets': int}
    """
    # 1) imposition dict
    impo = getattr(deliverable, "imposition", None)
    if isinstance(impo, dict):
        inner = int(impo.get("inner_sheets") or impo.get("inner_sheet_count") or impo.get("inner") or 0)
        cover = int(impo.get("cover_sheets") or impo.get("cover_sheet_count") or impo.get("cover") or 0)
        if inner or cover:
            return {"inner_sheets": inner, "cover_sheets": cover}

    # 2) direct attributes
    inner = getattr(deliverable, "inner_sheets", None)
    cover = getattr(deliverable, "cover_sheets", None)
    if inner is not None or cover is not None:
        return {"inner_sheets": int(inner or 0), "cover_sheets": int(cover or 0)}

    # 3) total_physical_sheets attribute or sheets/sheet_count
    total = getattr(deliverable, "total_physical_sheets", None) or getattr(deliverable, "sheets", None) or getattr(deliverable, "sheet_count", None)
    if total is not None:
        # assume all are inner run unless cover explicitly present
        return {"inner_sheets": int(total or 0), "cover_sheets": 0}

    # 4) nothing found -> return zeros and let the caller handle warnings
    return {"inner_sheets": 0, "cover_sheets": 0}


# ---------- Run cost computation ----------
def compute_print_run_cost(sheet_count: int, price_proxy: SimpleNamespace, *, is_cover: bool = False, extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Compute costs for a run (inner or cover) using a simple price proxy.
    """
    extras = extras or {}
    sc = int(sheet_count or 0)
    if sc <= 0:
        return {
            "sheet_count": 0,
            "price_per_sheet": Decimal("0.00"),
            "setup_cost": Decimal("0.00"),
            "makeready_cost": Decimal("0.00"),
            "waste_cost": Decimal("0.00"),
            "running_cost": Decimal("0.00"),
            "finishing_cost": Decimal("0.00"),
            "extras_cost": Decimal("0.00"),
            "total_run_cost": Decimal("0.00"),
            "warnings": ["zero sheet_count"],
        }

    pps = _to_decimal(getattr(price_proxy, "price_per_sheet", None), Decimal("0.00"))
    setup = _to_decimal(getattr(price_proxy, "setup_cost", None), Decimal("0.00"))
    makeready = _to_decimal(getattr(price_proxy, "makeready_cost", None), Decimal("0.00"))
    waste_percent = _to_decimal(getattr(price_proxy, "waste_percent", None), Decimal("0.00"))
    finishing = _to_decimal(getattr(price_proxy, "finishing_cost_per_sheet", None), Decimal("0.00"))

    warnings = []
    if pps == Decimal("0.00"):
        warnings.append("price_per_sheet is zero")

    # waste is applied as % of sheets (rounded)
    waste_sheets = int((Decimal(sc) * (waste_percent / Decimal("100"))).to_integral_value(rounding=ROUND_HALF_UP)) if waste_percent > 0 else 0
    waste_cost = (Decimal(waste_sheets) * pps).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    running_cost = (Decimal(sc) * pps).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    finishing_cost = (Decimal(sc) * finishing).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    extras_cost = Decimal("0.00")
    for k, v in (extras or {}).items():
        dv = _to_decimal(v, Decimal("0.00"))
        if k.endswith("_per_sheet"):
            extras_cost += (Decimal(sc) * dv)
        elif k.endswith("_flat"):
            extras_cost += dv
        else:
            extras_cost += dv

    total_run = (running_cost + waste_cost + setup + makeready + finishing_cost + extras_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "sheet_count": sc,
        "price_per_sheet": pps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "setup_cost": setup.quantize(Decimal("0.01")),
        "makeready_cost": makeready.quantize(Decimal("0.01")),
        "waste_percent": waste_percent,
        "waste_sheets": waste_sheets,
        "waste_cost": waste_cost,
        "running_cost": running_cost,
        "finishing_cost": finishing_cost,
        "extras_cost": extras_cost.quantize(Decimal("0.01")),
        "total_run_cost": total_run,
        "warnings": warnings,
    }


# ---------- Top-level cost (simplified) ----------
def compute_total_cost(deliverable: Any, price_obj: Optional[Any] = None, *, extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Compute total cost using deliverable-provided sheet counts (preferred).

    If price_obj is None, try to auto-find a DigitalPrintPrice.
    """
    extras = extras or {}
    warnings = []

    # auto-find price row if not provided
    if price_obj is None:
        price_obj = _auto_find_price_obj(deliverable)

    # build price proxy (deliverable overrides price_obj)
    price_proxy = _build_price_proxy_from(deliverable, price_obj)

    # get sheet counts from deliverable imposition/attributes
    sheets = _get_sheet_counts_from_deliverable(deliverable)
    inner_sheets = int(sheets.get("inner_sheets", 0) or 0)
    cover_sheets = int(sheets.get("cover_sheets", 0) or 0)

    # if we have only unit_price on proxy, try to convert using items_per_sheet if present on deliverable.imposition
    if getattr(price_proxy, "price_per_sheet", Decimal("0.00")) == Decimal("0.00") and getattr(price_proxy, "unit_price", None) is not None:
        # try to find items_per_sheet in imposition dict
        impo = getattr(deliverable, "imposition", None) or {}
        items_on_sheet = impo.get("items_per_sheet") or impo.get("pages_per_physical_sheet")
        try:
            ips = int(items_on_sheet) if items_on_sheet else None
            if ips and ips > 0:
                price_proxy.price_per_sheet = (_to_decimal(price_proxy.unit_price) * Decimal(ips)).quantize(Decimal("0.01"))
        except Exception:
            pass

    # inner run cost
    inner_run = compute_print_run_cost(inner_sheets, price_proxy, is_cover=False, extras=extras)
    warnings.extend(inner_run.get("warnings", []) or [])

    # cover run cost (use cover_price_per_sheet if available)
    cover_run = None
    if cover_sheets > 0:
        cover_proxy = price_proxy
        cover_pps = getattr(price_proxy, "cover_price_per_sheet", None)
        if cover_pps and cover_pps != Decimal("0.00"):
            # create a shallow copy proxy for cover price
            cover_proxy = SimpleNamespace(**{
                "price_per_sheet": _to_decimal(cover_pps),
                "setup_cost": getattr(price_proxy, "setup_cost", Decimal("0.00")),
                "makeready_cost": getattr(price_proxy, "makeready_cost", Decimal("0.00")),
                "waste_percent": getattr(price_proxy, "waste_percent", Decimal("0.00")),
                "finishing_cost_per_sheet": getattr(price_proxy, "finishing_cost_per_sheet", Decimal("0.00")),
                "minimum_charge": getattr(price_proxy, "minimum_charge", Decimal("0.00")),
                "currency": getattr(price_proxy, "currency", "KES"),
            })
        cover_run = compute_print_run_cost(cover_sheets, cover_proxy, is_cover=True, extras=extras)
        warnings.extend(cover_run.get("warnings", []) or [])

    total_cost = inner_run.get("total_run_cost", Decimal("0.00")) or Decimal("0.00")
    if cover_run:
        total_cost += cover_run.get("total_run_cost", Decimal("0.00")) or Decimal("0.00")

    # minimum charge (from proxy)
    min_charge = _to_decimal(getattr(price_proxy, "minimum_charge", None), Decimal("0.00"))
    if min_charge > Decimal("0.00") and total_cost < min_charge:
        warnings.append(f"Applied minimum charge: {min_charge}")
        total_cost = min_charge

    currency = getattr(price_proxy, "currency", "KES") or "KES"
    total_cost = total_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "sheets": {"inner_sheets": inner_sheets, "cover_sheets": cover_sheets},
        "runs": {"inner": inner_run, "cover": cover_run},
        "total_cost": total_cost,
        "total_cost_formatted": _format_currency(total_cost, currency=currency),
        "warnings": warnings,
    }
