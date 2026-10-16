"""NCET BCA flexible enrollment and consent-based public student showcase.

Public profiles contain only explicitly published fields. Private email/mobile and
confidential HOD requests are never returned by anonymous API or HTML routes.
"""
from __future__ import annotations

import io
import json
import re
import secrets
from datetime import datetime
from html import escape
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession, Mapped, mapped_column

from .database import Base, User, AuditLog, utcnow, get_db
from .student_models import BCAStudent
from .student_services import BCA_DEPARTMENT, USN_RE, can_manage_bca
from .security import current, csrf_required, hash_password

router = APIRouter(tags=['NCET student enrollment and showcase'])
URL_ROOT = 'https://ncet-verifyflow.onrender.com'
MAX_BATCH = 100

class StudentShowcase(Base):
    __tablename__ = 'bca_student_showcases'
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),unique=True,index=True)
    mobile_private: Mapped[str] = mapped_column(String(20),default='')
    email_private: Mapped[str] = mapped_column(String(180),default='')
    about: Mapped[str] = mapped_column(Text,default='')
    skills_json: Mapped[str] = mapped_column(Text,default='[]')
    certificates_json: Mapped[str] = mapped_column(Text,default='[]')
    published: Mapped[bool] = mapped_column(Boolean,default=False,index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utcnow)

class EnrollmentItem(BaseModel):
    usn: str
    full_name: str = Field(default='',max_length=130)
    semester: int = Field(default=1,ge=1,le=8)

class EnrollmentBody(BaseModel):
    students: list[EnrollmentItem] = Field(min_length=1,max_length=MAX_BATCH)

class FacultyUpdate(BaseModel):
    full_name: str = Field(min_length=3,max_length=130)
    semester: int = Field(ge=1,le=8)

class Certificate(BaseModel):
    title: str = Field(min_length=3,max_length=120)
    issuer: str = Field(min_length=2,max_length=120)
    proof_url: str = Field(min_length=12,max_length=650)

class ShowcaseEdit(BaseModel):
    full_name: str = Field(min_length=3,max_length=130)
    mobile: str = Field(default='',max_length=20)
    email: str = Field(default='',max_length=180)
    about: str = Field(default='',max_length=900)
    skills: list[str] = Field(default_factory=list,max_length=15)
    certificates: list[Certificate] = Field(default_factory=list,max_length=8)
    publish: bool = False


def valid_name(name:str)->bool:
    return 3<=len(name)<=130 and name[0] not in '=+-@' and not any(ord(c)<32 for c in name)


def validate_enrollment(items:list[EnrollmentItem])->list[tuple[str,str,int]]:
    result=[];seen=set()
    for i,item in enumerate(items,1):
        usn=item.usn.strip().upper()
        name=item.full_name.strip()
        if not USN_RE.fullmatch(usn):raise HTTPException(422,f'Invalid USN at entry {i}; expected 1NC followed by letters or digits.')
        if name and not valid_name(name):raise HTTPException(422,f'Invalid student name at entry {i}.')
        if usn in seen:raise HTTPException(422,f'Duplicate USN at entry {i}.')
        seen.add(usn);result.append((usn,name,item.semester))
    return result


def create_students(db, actor, items:list[EnrollmentItem]):
    can_manage_bca(actor)
    values=validate_enrollment(items)
    if db.query(User.id).filter(User.username.in_([u.lower() for u,n,s in values])).first() or \
       db.query(BCAStudent.id).filter(BCAStudent.usn.in_([u for u,n,s in values])).first():
        raise HTTPException(409,'One or more USNs are already enrolled. No accounts were created.')
    creds=[]
    try:
        for usn,name,semester in values:
            password=secrets.token_urlsafe(24)
            # This is deliberately not a guessable USN-derived password.
            user=User(username=usn.lower(),display_name=name or 'Registration pending',
                      role='student',department=BCA_DEPARTMENT,
                      password_hash=hash_password(password),active=True)
            db.add(user);db.flush()
            db.add(BCAStudent(user_id=user.id,usn=usn,semester=semester,must_change_password=True))
            creds.append({'usn':usn,'name':name,'semester':semester,'temporary_password':password})
        db.add(AuditLog(actor_id=actor.id,event='bca.flexible_enrollment',detail=f'{len(values)} new USNs'))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Duplicate student account: the batch was not imported.')
    return {'created':len(creds),'credentials':creds}


@router.post('/api/bca/students/enroll')
def enroll(body:EnrollmentBody,actor:User=Depends(csrf_required),db:DbSession=Depends(get_db)):
    return create_students(db,actor,body.students)


@router.post('/api/bca/students/import-excel')
async def import_excel(file:UploadFile=File(...),actor:User=Depends(csrf_required),db:DbSession=Depends(get_db)):
    can_manage_bca(actor)
    if not (file.filename or '').lower().endswith('.xlsx'):
        raise HTTPException(422,'Upload an .xlsx spreadsheet.')
    content=await file.read(350_001)
    if len(content)>350_000:raise HTTPException(413,'Spreadsheet must be smaller than 350 KB.')
    from openpyxl import load_workbook
    try:
        book=load_workbook(io.BytesIO(content),read_only=True,data_only=True)
        sheet=book.active
        iterator=sheet.iter_rows(min_row=1,max_row=102,values_only=True)
        header=tuple(str(c or '').strip().lower() for c in next(iterator))
        if header not in (('usn','full_name','semester'),('usn','name','semester'),('usn','full_name'),('usn','name'),('usn',)):
            raise ValueError('First row must contain USN, optional full_name, optional semester.')
        parsed=[]
        for row in iterator:
            if not row or not any(c is not None and str(c).strip() for c in row):continue
            if len(parsed)>=100:raise ValueError('Maximum 100 student rows per spreadsheet.')
            usn=str(row[0] or '').strip()
            name=str(row[1] or '').strip() if len(row)>1 else ''
            semester=int(row[2] or 1) if len(row)>2 else 1
            parsed.append(EnrollmentItem(usn=usn,full_name=name,semester=semester))
    except Exception as exc:
        raise HTTPException(422,'Invalid Excel roster. Check the headers, USNs and semesters.') from exc
    finally:
        if 'book' in locals():book.close()
    if not parsed:raise HTTPException(422,'The spreadsheet is empty.')
    return create_students(db,actor,parsed)


@router.patch('/api/bca/students/{usn}')
def faculty_edit(usn:str,body:FacultyUpdate,actor:User=Depends(csrf_required),db:DbSession=Depends(get_db)):
    can_manage_bca(actor)
    found=(db.query(User,BCAStudent).join(BCAStudent,BCAStudent.user_id==User.id)
           .filter(BCAStudent.usn==usn.upper()).first())
    if not found:raise HTTPException(404,'Student USN not found.')
    name=body.full_name.strip()
    if not valid_name(name):raise HTTPException(422,'Enter a valid student name.')
    user,student=found
    user.display_name=name;student.semester=body.semester
    # Changing official enrollment data requires the student to explicitly republish.
    showcase=db.query(StudentShowcase).filter(StudentShowcase.student_id==user.id).first()
    if showcase:showcase.published=False
    db.add(AuditLog(actor_id=actor.id,event='bca.student_details_updated',detail=student.usn))
    db.commit()
    return {'ok':True,'publication_review_required':bool(showcase)}


def _my_student(db,user):
    if user.role!='student':raise HTTPException(403,'Student account required.')
    found=db.query(BCAStudent).filter(BCAStudent.user_id==user.id).first()
    if not found:raise HTTPException(403,'Enrollment record missing.')
    return found


PUBLIC_EMAIL_PATTERN=re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
PUBLIC_PHONE_PATTERN=re.compile(r'(?<!\w)\+?\d[\d() .\-]{7,}\d(?!\w)')


def check_public_text(text:str)->None:
    if PUBLIC_EMAIL_PATTERN.search(text) or PUBLIC_PHONE_PATTERN.search(text):
        raise HTTPException(422,'Remove email addresses and phone numbers from fields published publicly.')


def validate_proof(url:str)->str:
    url=url.strip()
    parts=urlsplit(url)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password:
        raise HTTPException(422,'Certificate proof must be a public HTTPS URL.')
    if parts.hostname.lower() in ('localhost','127.0.0.1','0.0.0.0') or parts.hostname.endswith('.local'):
        raise HTTPException(422,'Invalid certificate host.')
    return url


def _showcase(db,user):
    return db.query(StudentShowcase).filter(StudentShowcase.student_id==user.id).first()


@router.get('/api/bca/showcase/me')
def my_showcase(user:User=Depends(current),db:DbSession=Depends(get_db)):
    student=_my_student(db,user)
    s=_showcase(db,user)
    return {'usn':student.usn,'full_name':user.display_name if user.display_name!='Registration pending' else '',
            'department':'Bachelor of Computer Applications','semester':student.semester,
            'must_change_password':student.must_change_password,
            'mobile':s.mobile_private if s else '', 'email':s.email_private if s else '',
            'about':s.about if s else '', 'skills':json.loads(s.skills_json) if s else [],
            'certificates':json.loads(s.certificates_json) if s else [],
            'published':s.published if s else False}


@router.put('/api/bca/showcase/me')
def edit_showcase(body:ShowcaseEdit,user:User=Depends(csrf_required),db:DbSession=Depends(get_db)):
    student=_my_student(db,user)
    if student.must_change_password:raise HTTPException(403,'Change your temporary password before editing your profile.')
    name=body.full_name.strip()
    if not valid_name(name):raise HTTPException(422,'Enter your complete name.')
    phone=body.mobile.strip()
    if phone and not re.fullmatch(r'\+?[0-9 ]{8,20}',phone):
        raise HTTPException(422,'Enter a valid private mobile number.')
    email=body.email.strip().lower()
    if email and (not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email) or len(email)>180):
        raise HTTPException(422,'Enter a valid private email address.')
    skills=[]
    for item in body.skills:
        value=item.strip()
        if not 2<=len(value)<=45 or any(ord(c)<32 for c in value):
            raise HTTPException(422,'Each skill must contain 2–45 printable characters.')
        if value.casefold() not in [x.casefold() for x in skills]:skills.append(value)
    check_public_text(name)
    check_public_text(body.about)
    for value in skills:check_public_text(value)
    certificates=[]
    for certificate in body.certificates:
        check_public_text(certificate.title)
        check_public_text(certificate.issuer)
        check_public_text(certificate.proof_url.split('?',1)[-1] if '?' in certificate.proof_url else '')
        certificates.append({'title':certificate.title.strip(),'issuer':certificate.issuer.strip(),
                            'proof_url':validate_proof(certificate.proof_url)})
    profile=_showcase(db,user)
    if not profile:
        profile=StudentShowcase(student_id=user.id)
        db.add(profile)
    user.display_name=name
    profile.mobile_private=phone;profile.email_private=email
    profile.about=body.about.strip()
    profile.skills_json=json.dumps(skills)
    profile.certificates_json=json.dumps(certificates)
    profile.published=bool(body.publish)
    profile.updated_at=utcnow()
    db.add(AuditLog(actor_id=user.id,event='bca.showcase_updated',
                    detail=f'{student.usn}: {"public" if profile.published else "private"}'))
    db.commit()
    return {'ok':True,'published':profile.published,'public_url':f'/students/profile/{student.usn}' if profile.published else None}


def public_query(db):
    return (db.query(User,BCAStudent,StudentShowcase)
            .join(BCAStudent,BCAStudent.user_id==User.id)
            .join(StudentShowcase,StudentShowcase.student_id==User.id)
            .filter(User.active.is_(True),BCAStudent.must_change_password.is_(False),
                    StudentShowcase.published.is_(True)))


def public_record(user,student,showcase):
    """Deliberate allowlist; private mobile and email never leave this function."""
    return {'name':user.display_name,'usn':student.usn,
            'department':'Bachelor of Computer Applications','semester':student.semester,
            'about':showcase.about,'skills':json.loads(showcase.skills_json),
            'certificates':json.loads(showcase.certificates_json)}


@router.get('/api/bca/directory')
def public_directory(q:str='',limit:int=30,db:DbSession=Depends(get_db)):
    if not 1<=limit<=50 or len(q)>60:raise HTTPException(422,'Invalid search.')
    query=public_query(db)
    if q.strip():
        term='%'+q.strip().replace('%','\\%').replace('_','\\_')+'%'
        query=query.filter(or_(BCAStudent.usn.ilike(term,escape='\\'),
                                User.display_name.ilike(term,escape='\\')))
    rows=query.order_by(BCAStudent.usn).limit(limit).all()
    return {'items':[{'name':u.display_name,'usn':p.usn,'department':'Bachelor of Computer Applications',
                       'skills':json.loads(s.skills_json)} for u,p,s in rows]}


@router.get('/api/bca/directory/{usn}')
def public_one(usn:str,db:DbSession=Depends(get_db)):
    if not USN_RE.fullmatch(usn.strip().upper()):raise HTTPException(404,'Profile unavailable.')
    record=public_query(db).filter(BCAStudent.usn==usn.strip().upper()).first()
    if not record:raise HTTPException(404,'Profile unavailable.')
    return public_record(*record)


@router.get('/students/profile/{usn}',response_class=HTMLResponse,include_in_schema=False)
def public_profile_html(usn:str,db:DbSession=Depends(get_db)):
    info=public_one(usn,db)
    name=escape(info['name']);sid=escape(info['usn'])
    description=escape((info['about'] or f'{name} studies Bachelor of Computer Applications at NCET.')[:155],quote=True)
    skills=''.join(f'<li>{escape(x)}</li>' for x in info['skills']) or '<li>Not added yet</li>'
    certs=''.join('<li><strong>'+escape(x['title'])+'</strong> · '+escape(x['issuer'])+
                  ' — <a rel="noopener noreferrer nofollow" target="_blank" href="'+escape(x['proof_url'],quote=True)+'">Public proof</a></li>'
                  for x in info['certificates']) or '<li>No certificates listed yet</li>'
    canonical=f'{URL_ROOT}/students/profile/{sid}'
    return HTMLResponse(f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} ({sid}) | NCET BCA</title><meta name="description" content="{description}">
<link rel="canonical" href="{canonical}"><link rel="icon" href="/static/ncet-official.webp">
<link rel="stylesheet" href="/static/bca.css"></head><body>
<header class="topnav"><div class="container nav-inner"><a class="brand" href="/students">
<img src="/static/ncet-official.webp" alt="NCET emblem">NCET BCA</a>
<nav class="navlinks"><a href="/students/directory">Student directory</a><a href="/students">Students</a></nav></div></header>
<main class="shell"><div class="panel"><span class="eyebrow">Student portfolio · voluntary publication</span>
<h1>{name}</h1><p class="muted">USN: {sid} · Bachelor of Computer Applications · Semester {info['semester']}</p>
<h2>About</h2><p>{escape(info['about']) or 'The student has not provided a description.'}</p>
<h2>Skills</h2><ul>{skills}</ul><h2>Certificates & proof</h2><ul>{certs}</ul>
<p class="muted">This profile is published by the student. NCET does not independently endorse linked credentials.</p>
<a class="btn" href="/students/directory">Back to student directory</a></div></main>
</body></html>''',headers={'Cache-Control':'public, max-age=120'})


@router.get('/students/directory',include_in_schema=False)
def directory_page():
    from pathlib import Path
    from fastapi.responses import FileResponse
    static=Path(__file__).resolve().parents[1]/'static'
    return FileResponse(static/'student-directory.html')


def published_sitemap_paths(db:DbSession)->list[str]:
    return ['/students/directory'] + [f'/students/profile/{p.usn}'
      for p in (db.query(BCAStudent).join(User,User.id==BCAStudent.user_id)
          .join(StudentShowcase,StudentShowcase.student_id==User.id)
          .filter(User.active.is_(True),BCAStudent.must_change_password.is_(False),
                  StudentShowcase.published.is_(True)).order_by(BCAStudent.usn).limit(10000).all())]
