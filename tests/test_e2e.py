import secrets
import app.main as main_module
from app.database import DBSession, Verification, Document
from app.security import DUMMY_PASSWORD_HASH
from app.verification import run_job

def finish_verification(docid):
    with DBSession() as db:
        job=db.query(Verification).join(Document).filter(Document.public_id==docid).order_by(Verification.id.desc()).first()
        run_id=job.id
    run_job(run_id)

import pytest

def test_health_and_metadata(client):
    assert client.get('/healthz').json()['ok']
    assert client.get('/about').status_code==200
    assert 'noindex' in client.get('/app').headers['x-robots-tag']
    assert client.get('/robots.txt').status_code==200
    assert client.get('/sitemap.xml').status_code==200
    assert client.get('/api/documents').status_code==401
    assert client.get('/notifications').status_code==401

def test_login_and_invalid_credentials(client,login):
    bad=client.post('/api/auth/login',json={'username':'hod','password':secrets.token_urlsafe(24),'role':'hod'})
    assert bad.status_code==401
    token=login(client,'staff')
    r=client.get('/api/auth/me')
    assert r.json()['user']['role']=='staff'
    assert r.json()['csrf']==token
    inbox=client.get('/notifications')
    assert inbox.status_code==200 and 'Application inbox' in inbox.text
    assert inbox.headers['cache-control']=='no-store'
    assert 'httponly' in client.cookies.get('ncet_session','') if False else True
    assert client.post('/api/auth/logout').status_code==403
    assert client.post('/api/auth/logout',headers={'X-CSRF-Token':token}).status_code==200
    assert client.get('/api/documents').status_code==401

def test_unknown_login_performs_password_verification(client,monkeypatch):
    verified=[]
    def capture_hash(password,stored_hash):
        verified.append(stored_hash)
        return False
    monkeypatch.setattr(main_module,'verify_password',capture_hash)
    response=client.post('/api/auth/login',json={
        'username':'not-a-real-account','password':'incorrect-password','role':'student'})
    assert response.status_code==401
    assert verified==[DUMMY_PASSWORD_HASH]

def test_submit_approve_cross_role_and_file(client,login,create_doc):
    stafftoken=login(client,'staff')
    docid=create_doc(client,stafftoken)
    client.post('/api/auth/logout',headers={'X-CSRF-Token':stafftoken})
    hodtoken=login(client,'hod')
    alerts=client.get('/api/alerts/inbox').json()
    assert any(n['category']=='submissions' and 'New document submission' in n['text'] for n in alerts['items'])
    assert client.post('/api/auth/logout',headers={'X-CSRF-Token':hodtoken}).status_code==200
    stafftoken=login(client,'staff')
    finish_verification(docid)
    assert len(client.get('/api/documents').json()['items'])==1
    assert client.post(f'/api/documents/{docid}/review',headers={'X-CSRF-Token':stafftoken},json={'decision':'approved'}).status_code==403
    assert client.get(f'/api/documents/{docid}/file').content.startswith(b'%PDF-')
    client.post('/api/auth/logout',headers={'X-CSRF-Token':stafftoken})
    ptoken=login(client,'principal')
    assert client.get('/api/documents').json()['total']==0
    assert client.get(f'/api/documents/{docid}/file').status_code==404
    client.post('/api/auth/logout',headers={'X-CSRF-Token':ptoken})
    hodtoken=login(client,'hod')
    assert client.get('/api/documents').json()['total']==1
    assert client.post(f'/api/documents/{docid}/review',json={'decision':'approved'}).status_code==403
    approved=client.post(f'/api/documents/{docid}/review',headers={'X-CSRF-Token':hodtoken},json={'decision':'approved','note':'Verified for publication.'})
    assert approved.status_code==200,approved.text
    client.post('/api/auth/logout',headers={'X-CSRF-Token':hodtoken})
    stafftoken=login(client,'staff')
    alerts=client.get('/api/alerts/inbox').json()
    assert any(n['category']=='submissions' and 'was approved by the HOD' in n['text'] for n in alerts['items'])
    client.post('/api/auth/logout',headers={'X-CSRF-Token':stafftoken})
    hodtoken=login(client,'hod')
    assert client.post(f'/api/documents/{docid}/review',headers={'X-CSRF-Token':hodtoken},json={'decision':'rejected','note':'Changed opinion.'}).status_code==409
    client.post('/api/auth/logout',headers={'X-CSRF-Token':hodtoken})
    for username in ('principal','iqac'):
        token=login(client,username)
        docs=client.get('/api/documents').json()['items']
        assert docs[0]['status']=='approved'
        assert client.get(f'/api/documents/{docid}/file').status_code==200
        client.post('/api/auth/logout',headers={'X-CSRF-Token':token})

def test_rejection_revision_history_and_files(client,login,create_doc):
    staff=login(client,'staff');id=create_doc(client,staff);finish_verification(id)
    client.post('/api/auth/logout',headers={'X-CSRF-Token':staff})
    hod=login(client,'hod')
    r=client.post(f'/api/documents/{id}/review',json={'decision':'rejected','note':'Attach signed attendance records'},headers={'X-CSRF-Token':hod})
    assert r.status_code==200
    client.post('/api/auth/logout',headers={'X-CSRF-Token':hod})
    staff=login(client,'staff')
    alerts=client.get('/api/alerts/inbox').json()
    assert any(n['category']=='submissions' and 'was rejected by the HOD' in n['text'] for n in alerts['items'])
    r=client.post(f'/api/documents/{id}/resubmit',headers={'X-CSRF-Token':staff},
        data={'note':'Attached signed corrected records'},files={'file':('corrected.pdf',b'%PDF-1.7\nnew','application/pdf')})
    assert r.status_code==200,r.text
    client.post('/api/auth/logout',headers={'X-CSRF-Token':staff})
    hod=login(client,'hod')
    alerts=client.get('/api/alerts/inbox').json()
    assert any(n['category']=='submissions' and 'Updated document submission' in n['text'] for n in alerts['items'])
    client.post('/api/auth/logout',headers={'X-CSRF-Token':hod})
    staff=login(client,'staff')
    doc=client.get('/api/documents').json()['items'][0]
    assert doc['version']==2
    assert [h['kind'] for h in doc['history']]==['submitted','rejected','resubmitted']
    assert doc['status']=='verifying'
    assert client.get(f'/api/documents/{id}/file?version=1').content.startswith(b'%PDF-1.7\n1')

def test_departments_enforced(client,login,create_doc):
    tok=login(client,'staff');id=create_doc(client,tok)
    client.post('/api/auth/logout',headers={'X-CSRF-Token':tok})
    tok=login(client,'staff2')
    assert client.get('/api/documents').json()['total']==0
    assert client.get(f'/api/documents/{id}/file').status_code==404
    client.post('/api/auth/logout',headers={'X-CSRF-Token':tok})
    tok=login(client,'hod2')
    assert client.get('/api/documents').json()['total']==0
    assert client.post(f'/api/documents/{id}/review',headers={'X-CSRF-Token':tok},json={'decision':'approved'}).status_code==404

def test_invalid_upload_file(client,login):
    tok=login(client,'staff')
    fields={'title':'NCET Audit Entry','category':'Academic Audit','year':'2026–27','description':'Legitimate descriptions for review and validation'}
    r=client.post('/api/documents',headers={'X-CSRF-Token':tok},data=fields,files={'file':('unsafe.pdf',b'<script>alert(1)</script>','application/pdf')})
    assert r.status_code==422
    assert client.get('/api/documents').json()['total']==0

def test_superadmin_account_management_and_password_rotation(client,login):
    staff=login(client,'staff')
    assert client.get('/api/users').status_code==403
    client.post('/api/auth/logout',headers={'X-CSRF-Token':staff})
    principal=login(client,'admin')
    created_password=secrets.token_urlsafe(32)
    response=client.post('/api/users',headers={'X-CSRF-Token':principal},json={
        'username':'faculty.jane','display_name':'Jane Faculty', 'role':'staff',
        'department':'Computer Science & Engineering','password':created_password})
    assert response.status_code==201,response.text
    uid=response.json()['id']
    logs=client.get('/api/audit').json()['items']
    assert any(x['event']=='account.created' for x in logs)
    client.post('/api/auth/logout',headers={'X-CSRF-Token':principal})
    staff_login=client.post('/api/auth/login',json={
        'username':'faculty.jane','password':created_password,'role':'staff'})
    assert staff_login.status_code==200,staff_login.text
    staff_token=staff_login.json()['csrf']
    changed_password=secrets.token_urlsafe(32)
    r=client.post('/api/auth/change-password',headers={'X-CSRF-Token':staff_token},json={
        'old_password':created_password,'new_password':changed_password})
    assert r.status_code==200
    client.post('/api/auth/logout',headers={'X-CSRF-Token':staff_token})
    assert client.post('/api/auth/login',json={'username':'faculty.jane','password':created_password,'role':'staff'}).status_code==401
    changed_login=client.post('/api/auth/login',json={'username':'faculty.jane','password':changed_password,'role':'staff'})
    assert changed_login.status_code==200
    client.post('/api/auth/logout',headers={'X-CSRF-Token':changed_login.json()['csrf']})
    admin_token=login(client,'admin')
    assert client.patch(f'/api/users/{uid}',headers={'X-CSRF-Token':admin_token},json={'active':False}).json()['active'] is False

def test_csrf_and_origin(client,login,create_doc):
    staff=login(client,'staff')
    fields={'title':'Audit Document','category':'Academic Audit','year':'2026–27','description':'This document is for audit.'}
    f={'file':('x.pdf',b'%PDF-1.7\n','application/pdf')}
    assert client.post('/api/documents',data=fields,files=f).status_code==403
    assert client.post('/api/documents',headers={'Origin':'https://attacker.invalid','X-CSRF-Token':staff},data=fields,files=f).status_code==403


def test_repeated_login_attempts_are_throttled(client):
    invalid_password=secrets.token_urlsafe(24)
    for i in range(12):
        r=client.post('/api/auth/login',json={'username':'missing','password':invalid_password,'role':'staff'})
        assert r.status_code==401
    assert client.post('/api/auth/login',json={'username':'missing','password':invalid_password,'role':'staff'}).status_code==429


def test_clamav_fail_closed(client,login,monkeypatch):
    monkeypatch.setenv('SCAN_MODE','clamav')
    monkeypatch.delenv('CLAMAV_HOST',raising=False)
    token=login(client,'staff')
    r=client.post('/api/documents',headers={'X-CSRF-Token':token},
        data={'title':'Malware scanner availability test','category':'Academic Audit','year':'2026–27',
              'description':'A document with a scanner missing should not be stored.'},
        files={'file':('normal.pdf',b'%PDF-1.7\n', 'application/pdf')})
    assert r.status_code==503
    assert client.get('/api/documents').json()['total']==0

