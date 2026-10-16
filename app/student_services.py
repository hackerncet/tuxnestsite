"""Authenticated NCMS BCA student support. Never expose submissions on public routes."""
import csv
import io
import re
import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession, selectinload
from .database import User, AuditLog, DBSession, get_db, utcnow
from .student_models import BCAStudent, StudentCase, StudentCaseMessage
from .security import current, csrf_required, as_role, as_role_mutation, hash_password

router=APIRouter(prefix='/api/bca', tags=['BCA student services'])
BCA_DEPARTMENT='Computer Applications'
BCA_DEPARTMENT_NAMES={'bca','computer applications','bachelor of computer applications'}
USN_RE=re.compile(r'^1NC[A-Z0-9]{5,14}$')
CATEGORIES={'academics','faculty','examinations','facilities','fees','documentation','request','other'}
STATES={'submitted','in_review','resolved','closed'}


def can_manage_bca(actor):
    if actor.role not in {'staff','hod','admin'} or (actor.role!='admin' and actor.department.strip().lower() not in BCA_DEPARTMENT_NAMES):
        raise HTTPException(403,'Only authorized BCA faculty can manage student enrollment.')


def student_profile(db,user):
    if user.role!='student':raise HTTPException(403,'Student access is required.')
    profile=db.query(BCAStudent).filter(BCAStudent.user_id==user.id).first()
    if not profile:raise HTTPException(403,'Student enrollment is incomplete.')
    return profile


def case_access(db,user,ref):
    case=db.query(StudentCase).options(selectinload(StudentCase.messages).selectinload(StudentCaseMessage.actor)).filter(StudentCase.reference==ref).first()
    if not case:raise HTTPException(404,'Request not found.')
    if user.role=='student':
        if case.student_id!=user.id:raise HTTPException(404,'Request not found.')
    elif user.role=='hod' and user.department.strip().lower() in BCA_DEPARTMENT_NAMES and case.department==BCA_DEPARTMENT:
        pass
    else:raise HTTPException(403,'You cannot access this request.')
    return case


def case_json(case,show_identity=False):
    result={'reference':case.reference,'subject':case.subject,'category':case.category,
            'description':case.description,'status':case.status,'created_at':case.created_at.isoformat(),
            'updated_at':case.updated_at.isoformat(),
            'messages':[{'author':'HOD' if m.actor.role=='hod' else 'Student','body':m.body,'created_at':m.created_at.isoformat()} for m in case.messages]}
    if show_identity:
        result['student']={'name':case.student.display_name,'usn':case.student.username.upper()}
    return result


class NewCase(BaseModel):
    category: str
    subject: str = Field(min_length=6,max_length=160)
    description: str = Field(min_length=15,max_length=4000)

class CaseReply(BaseModel):
    message: str = Field(min_length=2,max_length=2000)

class CaseStatus(BaseModel):
    status: str
    note: str = Field(default='',max_length=1000)


@router.get('/me')
def get_student_profile(user:User=Depends(as_role('student')),db:DbSession=Depends(get_db)):
    p=student_profile(db,user)
    return {'usn':p.usn,'name':user.display_name,'semester':p.semester,'must_change_password':p.must_change_password}

@router.post('/complete-account')
def complete_account(user:User=Depends(as_role_mutation('student')),db:DbSession=Depends(get_db)):
    # Password change is performed by the existing password-change endpoint; this only acknowledges it.
    p=student_profile(db,user)
    if p.must_change_password:
        raise HTTPException(409,'Change your initial password in Account Settings before filing a request.')
    return {'ok':True}

@router.post('/students/import')
async def import_students(file:UploadFile=File(...), actor:User=Depends(as_role_mutation('staff','hod','admin')),
                          db:DbSession=Depends(get_db)):
    can_manage_bca(actor)
    raw=await file.read(150_001)
    if len(raw)>150_000:raise HTTPException(413,'CSV must be smaller than 150 KB.')
    try:
        content=raw.decode('utf-8-sig')
        reader=csv.DictReader(io.StringIO(content,newline=''))
        if not reader.fieldnames or set(reader.fieldnames)!={'usn','full_name','semester'}:
            raise ValueError('CSV headers must be exactly: usn,full_name,semester')
        rows=list(reader)
    except (UnicodeError,csv.Error,ValueError) as exc:
        raise HTTPException(422,str(exc)) from exc
    if not 1<=len(rows)<=100:raise HTTPException(422,'Upload between 1 and 100 students per CSV.')
    seen=set();parsed=[]
    for n,row in enumerate(rows,2):
        if None in row or any(v is None for v in row.values()):raise HTTPException(422,f'CSV row {n} is malformed.')
        usn=str(row['usn']).strip().upper();full_name=str(row['full_name']).strip()
        try:semester=int(str(row['semester']).strip())
        except ValueError:semester=0
        if not USN_RE.fullmatch(usn):raise HTTPException(422,f'Invalid USN at row {n}; expected 1NC followed by 5–14 letters/digits.')
        if not 3<=len(full_name)<=130 or full_name[0] in '=+-@' or any(ord(ch)<32 for ch in full_name):raise HTTPException(422,f'Invalid student name at row {n}.')
        if not 1<=semester<=8:raise HTTPException(422,f'Invalid semester at row {n}.')
        if usn in seen:raise HTTPException(422,f'Duplicate USN at row {n}.')
        seen.add(usn);parsed.append((usn,full_name,semester))
    usernames=[usn.lower() for usn,_,_ in parsed]
    if db.query(User.id).filter(User.username.in_(usernames)).first() or db.query(BCAStudent.id).filter(BCAStudent.usn.in_(list(seen))).first():
        raise HTTPException(409,'At least one student already exists. No accounts were imported.')
    credentials=[]
    try:
        for usn,name,semester in parsed:
            password=secrets.token_urlsafe(20)
            student=User(username=usn.lower(),display_name=name,role='student',department=BCA_DEPARTMENT,
                         password_hash=hash_password(password),active=True)
            db.add(student);db.flush()
            db.add(BCAStudent(user_id=student.id,usn=usn,semester=semester,must_change_password=True))
            credentials.append({'usn':usn,'name':name,'semester':semester,'temporary_password':password})
        db.add(AuditLog(actor_id=actor.id,event='bca.students_imported',detail=f'{len(parsed)} students'))
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Student enrollment conflict; no accounts were imported.')
    # Credentials returned ONCE over authenticated TLS. Never log or store their cleartext.
    return {'created':len(credentials),'credentials':credentials}

@router.get('/students')
def list_students(actor:User=Depends(as_role('staff','hod','admin')),db:DbSession=Depends(get_db)):
    can_manage_bca(actor)
    items=db.query(User,BCAStudent).join(BCAStudent,BCAStudent.user_id==User.id).order_by(BCAStudent.usn).limit(1000).all()
    return {'items':[{'usn':p.usn,'name':u.display_name,'semester':p.semester,'active':u.active} for u,p in items]}

@router.get('/cases')
def list_cases(user:User=Depends(current),db:DbSession=Depends(get_db)):
    if user.role=='student':
        student_profile(db,user)
        base=db.query(StudentCase).filter(StudentCase.student_id==user.id)
    elif user.role=='hod' and user.department.strip().lower() in BCA_DEPARTMENT_NAMES:
        base=db.query(StudentCase).filter(StudentCase.department==BCA_DEPARTMENT)
    else:raise HTTPException(403,'Student or BCA HOD access required.')
    items=base.order_by(StudentCase.created_at.desc(),StudentCase.id.desc()).limit(200).all()
    return {'items':[{'reference':x.reference,'subject':x.subject,'category':x.category,'status':x.status,'created_at':x.created_at.isoformat()} for x in items]}

@router.post('/cases',status_code=201)
def create_case(body:NewCase,user:User=Depends(as_role_mutation('student')),db:DbSession=Depends(get_db)):
    profile=student_profile(db,user)
    if profile.must_change_password:raise HTTPException(403,'Change your temporary password before submitting a request.')
    if body.category not in CATEGORIES:raise HTTPException(422,'Select a valid category.')
    recent=db.query(func.count(StudentCase.id)).filter(StudentCase.student_id==user.id,StudentCase.created_at>=utcnow()-timedelta(hours=24)).scalar()
    if recent>=10:raise HTTPException(429,'You have reached the daily request limit. Follow up on an existing request instead.')
    case=StudentCase(reference='NCMS-BCA-'+secrets.token_hex(6).upper(),student_id=user.id,
                     department=BCA_DEPARTMENT,category=body.category,subject=body.subject.strip(),description=body.description.strip(),status='submitted')
    if len(case.subject)<6 or len(case.description)<15:raise HTTPException(422,'Add a detailed subject and description.')
    db.add(case);db.add(AuditLog(actor_id=user.id,event='bca.case_submitted',detail=case.reference));db.commit()
    return {'reference':case.reference,'status':case.status}

@router.get('/cases/{reference}')
def get_case(reference:str,user:User=Depends(current),db:DbSession=Depends(get_db)):
    case=case_access(db,user,reference)
    return case_json(case,show_identity=user.role=='hod')

@router.post('/cases/{reference}/messages')
def send_message(reference:str,body:CaseReply,user:User=Depends(csrf_required),db:DbSession=Depends(get_db)):
    case=case_access(db,user,reference)
    if case.status=='closed':raise HTTPException(409,'Closed requests cannot receive messages.')
    message=body.message.strip()
    if len(message)<2:raise HTTPException(422,'Message must not be empty.')
    db.add(StudentCaseMessage(case_id=case.id,actor_id=user.id,body=message))
    case.updated_at=utcnow()
    db.add(AuditLog(actor_id=user.id,event='bca.case_replied',detail=case.reference))
    db.commit();return {'ok':True}

@router.patch('/cases/{reference}/status')
def update_case_status(reference:str,body:CaseStatus,user:User=Depends(as_role_mutation('hod')),db:DbSession=Depends(get_db)):
    case=case_access(db,user,reference)
    if body.status not in STATES or body.status=='submitted':raise HTTPException(422,'Invalid status.')
    if case.status=='closed':raise HTTPException(409,'Case is already closed.')
    note=body.note.strip()
    if body.status in {'resolved','closed'} and len(note)<5:
        raise HTTPException(422,'Provide an explanation of at least five characters.')
    case.status=body.status;case.updated_at=utcnow()
    if note:db.add(StudentCaseMessage(case_id=case.id,actor_id=user.id,body=note))
    db.add(AuditLog(actor_id=user.id,event='bca.case_status',detail=f'{case.reference}: {body.status}'))
    db.commit();return {'ok':True,'status':case.status}
