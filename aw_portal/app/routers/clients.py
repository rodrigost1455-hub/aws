from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..auth import current_user
from ..database import get_db
from ..serialization import calc_to_camel, client_to_dict

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("")
def list_clients(db: Session = Depends(get_db), user=Depends(current_user)):
    out = []
    for c in crud.list_clients(db):
        out.append(client_to_dict(c, crud.last_report_date(db, c.id)))
    return out


@router.post("", status_code=201)
def create_client(payload: schemas.ClientIn, db: Session = Depends(get_db), user=Depends(current_user)):
    c = crud.create_client(db, payload)
    db.commit()
    db.refresh(c)
    return client_to_dict(c, crud.last_report_date(db, c.id))


@router.get("/{cid}")
def get_client(cid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    c = crud.get_client(db, cid)
    if not c:
        raise HTTPException(404, "client not found")
    return client_to_dict(c, crud.last_report_date(db, cid))


@router.put("/{cid}")
def put_client(cid: str, payload: schemas.ClientIn, db: Session = Depends(get_db), user=Depends(current_user)):
    c = crud.get_client(db, cid)
    if not c:
        raise HTTPException(404, "client not found")
    crud.update_client(db, c, payload)
    db.commit()
    db.refresh(c)
    return client_to_dict(c, crud.last_report_date(db, cid))


@router.get("/{cid}/last-values")
def last_values(cid: str, db: Session = Depends(get_db), user=Depends(current_user)):
    c = crud.get_client(db, cid)
    if not c:
        raise HTTPException(404, "client not found")
    lv = crud.last_values(db, cid)
    if lv is None:
        return JSONResponse(
            {"quarter": None, "balances": {}, "liabilities": {}, "zillow": 0, "privateReserve": 0}
        )
    return {
        "quarter": lv["quarter"],
        "balances": {k: float(v) for k, v in lv["balances"].items()},
        "liabilities": {k: float(v) for k, v in lv["liabilities"].items()},
        "zillow": float(lv["zillow"]),
        "privateReserve": float(lv["private_reserve"]),
    }


@router.post("/{cid}/calculate")
def calculate(
    cid: str,
    payload: schemas.CalculateIn,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    c = crud.get_client(db, cid)
    if not c:
        raise HTTPException(404, "client not found")
    res = crud.calculate_for(c, payload)
    return calc_to_camel(res)
