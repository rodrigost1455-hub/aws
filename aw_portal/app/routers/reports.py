from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from .. import canva as canva_client
from .. import crud, ids, models, schemas
from ..auth import current_user
from ..database import get_db
from ..pdf_generator import pdf_filename, render_html, render_pdf
from ..serialization import calc_to_camel, client_to_dict, report_to_dict

client_router = APIRouter(prefix="/api/clients", tags=["reports"])
report_router = APIRouter(prefix="/api/reports", tags=["reports"])


def _required_field_keys(c: models.Client) -> list[str]:
    keys = ["reserve"]
    if c.trust_exists:
        keys.append("zillow")
    for a in c.accounts:
        keys.append(f"bal:{a.id}")
    for l in c.liabilities:
        keys.append(f"liab:{l.id}")
    return keys


@client_router.get("/{cid}/reports")
def list_reports(cid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    c = crud.get_client(db, cid)
    if not c:
        raise HTTPException(404, "client not found")
    return [report_to_dict(r) for r in crud.list_reports(db, cid)]


@client_router.post("/{cid}/reports", status_code=201)
def create_report(
    cid: str,
    payload: schemas.ReportIn,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    c = crud.get_client(db, cid)
    if not c:
        raise HTTPException(404, "client not found")

    # Build the submitted-key set the server can see.
    submitted: set[str] = set()
    for aid, v in (payload.balances or {}).items():
        if v is not None:
            submitted.add(f"bal:{aid}")
    for lid, v in (payload.liabilities or {}).items():
        if v is not None:
            submitted.add(f"liab:{lid}")
    if payload.private_reserve is not None:
        submitted.add("reserve")
    if c.trust_exists and payload.zillow is not None:
        submitted.add("zillow")

    required = set(_required_field_keys(c))
    missing = sorted(required - submitted)
    if missing:
        return JSONResponse(status_code=422, content={"detail": "missing required field_keys", "missing": missing})

    # Server-authoritative calc (ignore any client-sent calc).
    calc_payload = schemas.CalculateIn(
        financials=payload.financials,
        balances=payload.balances,
        liabilities=payload.liabilities,
        zillow=payload.zillow or 0,
        private_reserve=payload.private_reserve,
    )
    calc = crud.calculate_for(c, calc_payload)

    fin_snap = {
        "financials": {
            "inflow": float(payload.financials.inflow),
            "outflow": float(payload.financials.outflow),
            "deductibles": float(payload.financials.deductibles),
        },
        "zillow": float(payload.zillow or 0),
        "private_reserve": float(payload.private_reserve),
    }
    calc_snap = {k: float(v) if isinstance(v, Decimal) else v for k, v in calc.as_dict().items()}

    r = models.Report(
        id=ids.report_id(),
        client_id=c.id,
        report_date=payload.date,
        quarter_label=payload.quarter,
        financials_snapshot=fin_snap,
        calc_snapshot=calc_snap,
        created_at=datetime.utcnow(),
    )
    for aid, v in (payload.balances or {}).items():
        r.entries.append(models.ReportEntry(id=ids.entry_id(), field_key=f"bal:{aid}", value=Decimal(str(v))))
    for lid, v in (payload.liabilities or {}).items():
        r.entries.append(models.ReportEntry(id=ids.entry_id(), field_key=f"liab:{lid}", value=Decimal(str(v))))
    r.entries.append(models.ReportEntry(id=ids.entry_id(), field_key="reserve", value=Decimal(str(payload.private_reserve))))
    if c.trust_exists:
        r.entries.append(models.ReportEntry(id=ids.entry_id(), field_key="zillow", value=Decimal(str(payload.zillow or 0))))
    # snapshot financials as entries for queryability
    for k in ("inflow", "outflow", "deductibles"):
        r.entries.append(models.ReportEntry(id=ids.entry_id(), field_key=k, value=Decimal(str(getattr(payload.financials, k)))))

    db.add(r)
    db.commit()
    db.refresh(r)

    return report_to_dict(r, calc_to_camel(calc))


@report_router.get("/{rid}")
def get_report(rid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    r = crud.get_report(db, rid)
    if not r:
        raise HTTPException(404, "report not found")
    return report_to_dict(r)


def _load_report_and_client(db: Session, rid: str) -> tuple[models.Report, models.Client]:
    r = crud.get_report(db, rid)
    if not r:
        raise HTTPException(404, "report not found")
    c = crud.get_client(db, r.client_id)
    if not c:
        raise HTTPException(404, "client not found")
    return r, c


@report_router.get("/{rid}/pdf")
def report_pdf(
    rid: str,
    type: str = Query(..., pattern="^(sacs|tcc)$"),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    r, c = _load_report_and_client(db, rid)
    client_dict = client_to_dict(c)
    report_dict = report_to_dict(r)

    body = render_pdf(type, client_dict, report_dict)
    fname = pdf_filename(client_dict, type, r.quarter_label)
    return Response(
        body,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


@report_router.get("/{rid}/preview", response_class=HTMLResponse)
def report_preview(
    rid: str,
    type: str = Query(..., pattern="^(sacs|tcc)$"),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    """Raw HTML — for fast iteration on the templates without WeasyPrint."""
    r, c = _load_report_and_client(db, rid)
    return HTMLResponse(render_html(type, client_to_dict(c), report_to_dict(r)))


@report_router.post("/{rid}/export-canva")
def export_canva(rid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    if not canva_client.is_configured():
        # 501 with a clear message — never breaks the PDF flow.
        raise HTTPException(status_code=501, detail="Canva export not configured (set CANVA_API_KEY)")

    r, c = _load_report_and_client(db, rid)
    client_dict = client_to_dict(c)
    report_dict = report_to_dict(r)

    uploads: dict[str, dict] = {}
    errors: dict[str, str] = {}
    for kind in ("sacs", "tcc"):
        try:
            pdf = render_pdf(kind, client_dict, report_dict)
            fname = pdf_filename(client_dict, kind, r.quarter_label)
            up = canva_client.upload_pdf(fname, pdf)
            uploads[kind] = {
                "assetId": up.asset_id,
                "assetUrl": up.asset_url,
                "designId": up.design_id,
                "designUrl": up.design_url,
            }
        except canva_client.CanvaError as e:
            errors[kind] = str(e)
        except Exception as e:  # never let Canva failures escape into PDF flow
            errors[kind] = f"unexpected error: {e}"

    if not uploads:
        # All attempts failed — surface a 502 with details.
        raise HTTPException(status_code=502, detail={"message": "Canva upload failed", "errors": errors})

    return {"reportId": rid, "uploads": uploads, "errors": errors or None}
