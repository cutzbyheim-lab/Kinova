import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import RequestContext, get_ctx, get_owned
from app.core.db import get_db
from app.models import Brand
from app.schemas.api import BrandIn, BrandOut, BrandPatch
from app.services.audit import audit

router = APIRouter(prefix="/api/brands", tags=["brands"])


@router.get("", response_model=list[BrandOut])
def list_brands(db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    return db.scalars(select(Brand).where(Brand.org_id == ctx.org_id).order_by(Brand.created_at.desc())).all()


@router.post("", response_model=BrandOut, status_code=201)
def create_brand(body: BrandIn, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    brand = Brand(org_id=ctx.org_id, **body.model_dump())
    db.add(brand)
    db.flush()
    audit(db, ctx, "brand.create", "brand", brand.id, name=brand.name)
    db.commit()
    return brand


@router.get("/{brand_id}", response_model=BrandOut)
def get_brand(brand_id: uuid.UUID, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    return get_owned(db, Brand, brand_id, ctx)


@router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(brand_id: uuid.UUID, body: BrandPatch, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    brand = get_owned(db, Brand, brand_id, ctx)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(brand, k, v)
    audit(db, ctx, "brand.update", "brand", brand.id)
    db.commit()
    return brand


@router.delete("/{brand_id}", status_code=204)
def delete_brand(brand_id: uuid.UUID, db: Session = Depends(get_db), ctx: RequestContext = Depends(get_ctx)):
    brand = get_owned(db, Brand, brand_id, ctx)
    db.delete(brand)
    audit(db, ctx, "brand.delete", "brand", brand_id)
    db.commit()
