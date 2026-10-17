"""Persistent in-app alerts, scoped to accounts and roles."""
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, Session
from .database import Base, User, get_db, utcnow
from .security import current, csrf_required

router=APIRouter(tags=['In-app notifications'])

class AppNotification(Base):
    __tablename__='app_notifications'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    recipient_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    text:Mapped[str]=mapped_column(String(280))
    link:Mapped[str]=mapped_column(String(220))
    category:Mapped[str]=mapped_column(String(32),index=True)
    seen:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,index=True)


def emit(db,users,text,link,category,exclude=None):
    if not link.startswith('/') or link.startswith('//'):raise ValueError('A local link is required.')
    for user_id in set(users):
        if user_id and user_id!=exclude:
            db.add(AppNotification(recipient_id=user_id,text=text[:280],link=link[:220],category=category[:32]))


def hod_recipients(db):
    from .student_services import BCA_DEPARTMENT_NAMES
    people=db.query(User).filter(User.active.is_(True),User.role=='hod').all()
    return [person.id for person in people if person.department.strip().lower() in BCA_DEPARTMENT_NAMES]


def all_members(db):
    return [item.id for item in db.query(User.id).filter(User.active.is_(True)).all()]


@router.get('/api/alerts/inbox')
def inbox(user:User=Depends(current),db:Session=Depends(get_db)):
    from .taskflow import TaskNotification
    current_items=db.query(AppNotification).filter(AppNotification.recipient_id==user.id).order_by(AppNotification.id.desc()).limit(80).all()
    tasks=db.query(TaskNotification).filter(TaskNotification.user_id==user.id).order_by(TaskNotification.id.desc()).limit(50).all()
    items=[{'id':f'a-{n.id}','text':n.text,'link':n.link,'category':n.category,'seen':n.seen,'at':n.created_at.isoformat()} for n in current_items]
    items.extend({'id':f't-{n.id}','text':n.text,'link':'/tasks','category':'tasks','seen':n.seen,'at':n.created_at.isoformat()} for n in tasks)
    items.sort(key=lambda n:n['at'],reverse=True)
    return {'unread':sum(not n['seen'] for n in items),'items':items[:100]}


@router.post('/api/alerts/{notification_id}/read')
def read(notification_id:str,user:User=Depends(csrf_required),db:Session=Depends(get_db)):
    try:prefix,key=notification_id.split('-',1);identity=int(key)
    except (ValueError,TypeError):raise HTTPException(422,'Invalid notification identifier.')
    if prefix=='a':
        notice=db.query(AppNotification).filter_by(id=identity,recipient_id=user.id).first()
    elif prefix=='t':
        from .taskflow import TaskNotification
        notice=db.query(TaskNotification).filter_by(id=identity,user_id=user.id).first()
    else:raise HTTPException(422,'Invalid notification identifier.')
    if not notice:raise HTTPException(404,'Notification not found.')
    notice.seen=True
    db.commit()
    return {'ok':True}
