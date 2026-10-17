"""Private, shared BCA project-contributions board. No DMs or public student records.

All endpoints require an active institutional session; students post under their verified USN.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session as DbSession

from .database import Base, User, AuditLog, get_db, utcnow
from .security import current, csrf_required
from .student_models import BCAStudent

router = APIRouter(prefix='/api/community', tags=['Authenticated BCA project collaboration'])
READ_ROLES = {'student','staff','hod','principal','iqac','admin'}
MOD_ROLES = {'admin','hod'}
MAX_POSTS_PER_DAY = 5
MAX_COMMENTS_PER_DAY = 30


class CollaborationProfile(Base):
    __tablename__ = 'collaboration_profiles'
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True, index=True)
    bio: Mapped[str] = mapped_column(String(360), default='')
    skills: Mapped[str] = mapped_column(String(220), default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CollaborationPost(Base):
    __tablename__ = 'collaboration_posts'
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), index=True)
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(Text)
    help_needed: Mapped[str] = mapped_column(String(280))
    state: Mapped[str] = mapped_column(String(18), default='open', index=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    author: Mapped[User] = relationship()
    comments: Mapped[list['CollaborationComment']] = relationship(order_by='CollaborationComment.id', back_populates='post')


class CollaborationComment(Base):
    __tablename__ = 'collaboration_comments'
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey('collaboration_posts.id', ondelete='CASCADE'), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), index=True)
    message: Mapped[str] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    post: Mapped[CollaborationPost] = relationship(back_populates='comments')
    author: Mapped[User] = relationship()


def viewer(user: User = Depends(current)):
    if user.role not in READ_ROLES:
        raise HTTPException(403, 'You cannot access this board.')
    return user


def writer(user: User = Depends(csrf_required)):
    if user.role not in READ_ROLES:
        raise HTTPException(403, 'You cannot participate in this board.')
    return user


def enrolled_student(db, user, *, ready=False):
    if user.role != 'student':
        raise HTTPException(403, 'Only BCA students can publish projects and edit student profiles.')
    record = db.query(BCAStudent).filter(BCAStudent.user_id == user.id).first()
    if not record:
        raise HTTPException(403, 'Student enrollment is required.')
    if ready and record.must_change_password:
        raise HTTPException(403, 'Change your temporary password before posting.')
    return record


def moderator(user):
    return user.role == 'admin' or (user.role == 'hod' and user.department.strip().lower() in {'bca','computer applications','bachelor of computer applications'})


def author_json(db, user):
    if user.role == 'student':
        student = db.query(BCAStudent).filter(BCAStudent.user_id == user.id).first()
        return {'name':user.display_name,'usn':student.usn if student else None,'role':'student'}
    return {'name':user.display_name,'usn':None,'role':user.role}


def post_json(db, post, viewer_user, *, include_comments=True):
    obj = {'id':post.id,'title':post.title,'description':post.description,'help_needed':post.help_needed,
           'state':post.state,'created_at':post.created_at.isoformat(),
           'author':author_json(db,post.author),'mine':post.student_id==viewer_user.id,
           'can_moderate':moderator(viewer_user)}
    if include_comments:
        obj['comments']=[{'id':c.id,'author':author_json(db,c.author),'message':c.message,
                          'created_at':c.created_at.isoformat()} for c in post.comments if not c.hidden]
    return obj


class ProfileEdit(BaseModel):
    bio: str = Field(default='',max_length=360)
    skills: str = Field(default='',max_length=220)

class PostCreate(BaseModel):
    title: str = Field(min_length=8,max_length=140)
    description: str = Field(min_length=30,max_length=3000)
    help_needed: str = Field(min_length=8,max_length=280)

class CommentCreate(BaseModel):
    message: str = Field(min_length=2,max_length=1200)

class PostUpdate(BaseModel):
    state: str


def moderation_audit(db, actor, action, target):
    db.add(AuditLog(actor_id=actor.id,event=action,detail=str(target)[:100]))


@router.get('/me')
def my_public_profile(user:User=Depends(viewer),db:DbSession=Depends(get_db)):
    if user.role!='student':
        return {'role':user.role,'is_student':False,'can_moderate':moderator(user)}
    student=enrolled_student(db,user)
    extra=db.query(CollaborationProfile).filter(CollaborationProfile.student_id==user.id).first()
    return {'role':'student','is_student':True,'must_change_password':student.must_change_password,
            'usn':student.usn,'name':user.display_name,'semester':student.semester,
            'bio':extra.bio if extra else '', 'skills':extra.skills if extra else '', 'can_moderate':False}


@router.get('/profiles')
def profiles(q:str='',offset:int=0,limit:int=25,user:User=Depends(viewer),db:DbSession=Depends(get_db)):
    if offset<0 or not 1<=limit<=50:raise HTTPException(422,'Invalid pagination.')
    query=db.query(User,BCAStudent).join(BCAStudent,BCAStudent.user_id==User.id).filter(User.active.is_(True))
    if q.strip():
        term='%'+q.strip()[:60].replace('%','\\%').replace('_','\\_')+'%'
        query=query.filter((User.display_name.ilike(term,escape='\\')) | (BCAStudent.usn.ilike(term,escape='\\')))
    users=query.order_by(BCAStudent.usn).offset(offset).limit(limit).all()
    return {'items':[{'name':u.display_name,'usn':s.usn,'semester':s.semester,
                      'bio':prof.bio if prof else '', 'skills':prof.skills if prof else ''}
                      for u,s in users for prof in [db.query(CollaborationProfile).filter(CollaborationProfile.student_id==u.id).first()]],
            'offset':offset,'limit':limit}


@router.get('/profiles/{usn}')
def get_profile(usn:str,user:User=Depends(viewer),db:DbSession=Depends(get_db)):
    found=db.query(User,BCAStudent).join(BCAStudent,BCAStudent.user_id==User.id).filter(BCAStudent.usn==usn.upper(),User.active.is_(True)).first()
    if not found:raise HTTPException(404,'Student profile not found.')
    u,p=found; extra=db.query(CollaborationProfile).filter(CollaborationProfile.student_id==u.id).first()
    return {'name':u.display_name,'usn':p.usn,'semester':p.semester,'bio':extra.bio if extra else '',
            'skills':extra.skills if extra else ''}


@router.put('/me')
def update_profile(body:ProfileEdit,user:User=Depends(writer),db:DbSession=Depends(get_db)):
    enrolled_student(db,user,ready=True)
    bio=body.bio.strip();skills=body.skills.strip()
    existing=db.query(CollaborationProfile).filter(CollaborationProfile.student_id==user.id).first()
    if existing:existing.bio=bio;existing.skills=skills;existing.updated_at=utcnow()
    else:db.add(CollaborationProfile(student_id=user.id,bio=bio,skills=skills))
    moderation_audit(db,user,'community.profile_updated',user.id)
    db.commit()
    return {'ok':True}


@router.get('/posts')
def list_posts(offset:int=0,limit:int=20,state:str='all',user:User=Depends(viewer),db:DbSession=Depends(get_db)):
    if offset<0 or not 1<=limit<=50:raise HTTPException(422,'Invalid pagination.')
    if state not in {'all','open','closed'}:raise HTTPException(422,'Invalid filter.')
    q=db.query(CollaborationPost).filter(CollaborationPost.hidden.is_(False))
    if state!='all':q=q.filter(CollaborationPost.state==state)
    posts=q.order_by(CollaborationPost.created_at.desc(),CollaborationPost.id.desc()).offset(offset).limit(limit).all()
    return {'items':[post_json(db,p,user,include_comments=False) for p in posts],'offset':offset,'limit':limit}


@router.post('/posts',status_code=201)
def create_post(body:PostCreate,user:User=Depends(writer),db:DbSession=Depends(get_db)):
    enrolled_student(db,user,ready=True)
    values=[body.title.strip(),body.description.strip(),body.help_needed.strip()]
    if len(values[0])<8 or len(values[1])<30 or len(values[2])<8:raise HTTPException(422,'Describe your project and the collaboration needed.')
    count=db.query(func.count(CollaborationPost.id)).filter(CollaborationPost.student_id==user.id,CollaborationPost.created_at>=utcnow()-timedelta(days=1)).scalar()
    if count>=MAX_POSTS_PER_DAY:raise HTTPException(429,'Daily project posting limit reached.')
    post=CollaborationPost(student_id=user.id,title=values[0],description=values[1],help_needed=values[2])
    from .notifications import emit, all_members
    db.add(post);db.flush();moderation_audit(db,user,'community.post_created',post.id)
    emit(db,all_members(db),'New student project collaboration opportunity.','/community','projects',exclude=user.id)
    db.commit()
    return {'id':post.id,'ok':True}


@router.get('/posts/{post_id}')
def get_post(post_id:int,user:User=Depends(viewer),db:DbSession=Depends(get_db)):
    post=db.get(CollaborationPost,post_id)
    if not post or post.hidden:raise HTTPException(404,'Project not found.')
    return post_json(db,post,user)


@router.post('/posts/{post_id}/comments',status_code=201)
def add_comment(post_id:int,body:CommentCreate,user:User=Depends(writer),db:DbSession=Depends(get_db)):
    if user.role=='student':enrolled_student(db,user,ready=True)
    post=db.get(CollaborationPost,post_id)
    if not post or post.hidden:raise HTTPException(404,'Project not found.')
    if post.state!='open':raise HTTPException(409,'This project is closed to new comments.')
    message=body.message.strip()
    if len(message)<2:raise HTTPException(422,'Write a comment.')
    count=db.query(func.count(CollaborationComment.id)).filter(CollaborationComment.author_id==user.id,
        CollaborationComment.created_at>=utcnow()-timedelta(days=1)).scalar()
    if count>=MAX_COMMENTS_PER_DAY:raise HTTPException(429,'Daily discussion limit reached.')
    comment=CollaborationComment(post_id=post_id,author_id=user.id,message=message)
    db.add(comment);db.flush();moderation_audit(db,user,'community.comment_added',comment.id);db.commit()
    return {'id':comment.id,'ok':True}


@router.patch('/posts/{post_id}')
def change_state(post_id:int,body:PostUpdate,user:User=Depends(writer),db:DbSession=Depends(get_db)):
    post=db.get(CollaborationPost,post_id)
    if not post or post.hidden:raise HTTPException(404,'Project not found.')
    if post.student_id!=user.id and not moderator(user):raise HTTPException(403,'Only the project owner or BCA HOD can change its status.')
    if body.state not in {'open','closed'}:raise HTTPException(422,'Invalid status.')
    post.state=body.state;post.updated_at=utcnow()
    moderation_audit(db,user,'community.post_state',f'{post.id}:{body.state}');db.commit()
    return {'ok':True,'state':post.state}


@router.post('/posts/{post_id}/hide')
def hide_post(post_id:int,user:User=Depends(writer),db:DbSession=Depends(get_db)):
    if not moderator(user):raise HTTPException(403,'Moderator access required.')
    post=db.get(CollaborationPost,post_id)
    if not post:raise HTTPException(404,'Project not found.')
    post.hidden=True;moderation_audit(db,user,'community.post_hidden',post.id);db.commit()
    return {'ok':True}


@router.post('/comments/{comment_id}/hide')
def hide_comment(comment_id:int,user:User=Depends(writer),db:DbSession=Depends(get_db)):
    if not moderator(user):raise HTTPException(403,'Moderator access required.')
    comment=db.get(CollaborationComment,comment_id)
    if not comment:raise HTTPException(404,'Comment not found.')
    comment.hidden=True;moderation_audit(db,user,'community.comment_hidden',comment.id);db.commit()
    return {'ok':True}
