"""Administrator-managed academic branches with immutable internal codes.

Names can change without altering HOD permissions, historical case departments,
or User.department codes. Disabling a branch blocks future enrollment, not logins.
"""
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Session as DbSession, Mapped, mapped_column
from .database import Base, User, AuditLog, get_db
from .security import current, as_role_mutation

router=APIRouter(tags=['Academic departments'])

class AcademicDepartment(Base):
    __tablename__='academic_departments'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(160),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(160),unique=True,index=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)

class DepartmentCreate(BaseModel):
    name:str=Field(min_length=2,max_length=160)

class DepartmentEdit(BaseModel):
    name:str|None=Field(default=None,min_length=2,max_length=160)
    active:bool|None=None

def clean_department_name(raw):
    name=' '.join(raw.strip().split())
    if len(name)<2 or len(name)>160 or name[0] in '=+-@' or any(ord(ch)<32 for ch in name):
        raise HTTPException(422,'Enter a valid department name (2–160 characters).')
    return name

def branch_option(db:DbSession,code:str,*,require_active=True):
    code=(code or '').strip()
    if not code:raise HTTPException(422,'Branch is required for every student.')
    result=db.query(AcademicDepartment).filter(AcademicDepartment.code==code).first()
    if not result or (require_active and not result.active):
        raise HTTPException(422,f'Branch "{code}" is not available. Choose an active department.')
    return result

def branch_name(db:DbSession,code:str)->str:
    result=db.query(AcademicDepartment).filter(AcademicDepartment.code==code).first()
    return result.name if result else code

def department_json(d):
    return {'code':d.code,'name':d.name,'active':d.active}

@router.get('/api/academic/departments')
def departments(actor:User=Depends(current),db:DbSession=Depends(get_db)):
    if actor.role not in ('admin','staff','hod'):
        raise HTTPException(403,'Authorized staff access required.')
    values=db.query(AcademicDepartment).order_by(AcademicDepartment.name).all()
    return {'items':[department_json(v) for v in values if actor.role=='admin' or v.active]}

@router.post('/api/admin/departments',status_code=201)
def add_department(body:DepartmentCreate,actor:User=Depends(as_role_mutation('admin')),db:DbSession=Depends(get_db)):
    name=clean_department_name(body.name)
    if db.query(AcademicDepartment).filter(AcademicDepartment.name.ilike(name)).first():
        raise HTTPException(409,'This department already exists.')
    # The immutable code is based on the original name; renamed labels never change scope.
    import secrets
    code='dept-'+secrets.token_hex(8)
    d=AcademicDepartment(code=code,name=name,active=True)
    db.add(d);db.add(AuditLog(actor_id=actor.id,event='admin.department_created',detail=f'{code}: {name}'))
    db.commit()
    return department_json(d)

@router.patch('/api/admin/departments/{code}')
def edit_department(code:str,body:DepartmentEdit,actor:User=Depends(as_role_mutation('admin')),db:DbSession=Depends(get_db)):
    dept=db.query(AcademicDepartment).filter(AcademicDepartment.code==code).with_for_update().first()
    if not dept:raise HTTPException(404,'Department not found.')
    if body.name is None and body.active is None:raise HTTPException(422,'No changes requested.')
    old=dept.name
    if body.name is not None:
        name=clean_department_name(body.name)
        duplicate=db.query(AcademicDepartment).filter(AcademicDepartment.name.ilike(name),AcademicDepartment.id!=dept.id).first()
        if duplicate:raise HTTPException(409,'A department already has that name.')
        dept.name=name
    if body.active is not None:dept.active=body.active
    db.add(AuditLog(actor_id=actor.id,event='admin.department_updated',
                    detail=f'{dept.code}: {old} -> {dept.name}; active={dept.active}'))
    db.commit()
    return department_json(dept)
