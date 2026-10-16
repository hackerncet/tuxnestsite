"""Practical HOD task allocation and non-destructive scoring tests."""
import json
from fastapi.testclient import TestClient
from app.database import DBSession,User
from app.taskflow import TaskItem, TaskNotification, TaskSubmission, run_task_once
from app.main import app
from app.ai_gateway import Provider,select_provider

PDF=b'%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n%%EOF'
RULE=[{'id':'header','title':'Mandatory heading','type':'required_heading','required':True,'value':'Academic Report','instructions':''}]


def _batch(c,csrf,n=2):
    r=c.post('/api/tasks/batches',headers={'X-CSRF-Token':csrf},
         data={'title':'October academic records batch'},
         files=[('files',(f'ref{i}.pdf',PDF,'application/pdf')) for i in range(n)])
    assert r.status_code==201,r.text
    return [x['id'] for x in c.get('/api/tasks').json()['items']]


def _staff_id():
    with DBSession() as db:return db.query(User).filter(User.username=='staff').first().id


def test_hod_bulk_assignment_notifications_and_holds(client,login):
    h=login(client,'hod'); ids=_batch(client,h,3)
    who=_staff_id()
    r=client.post('/api/tasks/assign',json={'task_ids':ids,'staff_id':who,'notes':'Prepare official report with proper headings.', 'rules':RULE},headers={'X-CSRF-Token':h})
    assert r.status_code==200,r.text
    assert r.json()['assigned']==3
    with TestClient(app) as staff:
        s=login(staff,'staff')
        inbox=staff.get('/api/tasks/notifications/inbox').json()
        assert inbox['unread']==3
        nid=inbox['items'][0]['id']
        assert staff.post(f'/api/tasks/notifications/{nid}/read',headers={'X-CSRF-Token':s}).status_code==200
        assert len(staff.get('/api/tasks').json()['items'])==3
        assert staff.get(f'/api/tasks/{ids[0]}/reference').status_code==200
        assert staff.post(f'/api/tasks/{ids[0]}/submit',headers={'X-CSRF-Token':s},files={'file':('done.pdf',PDF,'application/pdf')}).status_code==201
    assert client.post(f'/api/tasks/{ids[1]}/hold',params={'hold':'true'},headers={'X-CSRF-Token':h}).json()['state']=='on_hold'
    assert client.post(f'/api/tasks/{ids[1]}/hold',params={'hold':'false'},headers={'X-CSRF-Token':h}).json()['state']=='assigned'


def test_permission_department_and_invalid_batch(client,login):
    h=login(client,'hod'); ids=_batch(client,h,1)
    for bad in (0,_staff_id()+10_000):
        r=client.post('/api/tasks/assign',headers={'X-CSRF-Token':h},json={'task_ids':ids,'staff_id':bad,'notes':'Some important task notes to staff.', 'rules':RULE})
        assert r.status_code==403
    assert client.post('/api/tasks/batches',headers={'X-CSRF-Token':h},data={'title':'Uploaded work'},files={'files':('bad.txt',b'x'*20,'text/plain')}).status_code==422
    with TestClient(app) as other:
        login(other,'hod2')
        assert other.get('/api/tasks').json()['items']==[]
        assert other.get(f'/api/tasks/{ids[0]}/reference').status_code==404
        token=other.get('/api/auth/me').json()['csrf']
        assert other.post('/api/tasks/assign',headers={'X-CSRF-Token':token},json={'task_ids':ids,'staff_id':_staff_id(),'notes':'Trying to assign someone else task.','rules':RULE}).status_code==403
    with TestClient(app) as staff:
        s=login(staff,'staff')
        assert staff.post('/api/tasks/assign',headers={'X-CSRF-Token':s},json={'task_ids':ids,'staff_id':_staff_id(),'notes':'Attempted staff assignment','rules':RULE}).status_code==403
        assert staff.get(f'/api/tasks/{ids[0]}/reference').status_code==404


def test_ai_missing_is_manual_review_not_rejection(client,login):
    h=login(client,'hod');id=_batch(client,h,1)[0]
    assert client.post('/api/tasks/assign',headers={'X-CSRF-Token':h},json={'task_ids':[id],'staff_id':_staff_id(), 'notes':'Prepare final document with all specified parts.','rules':RULE}).status_code==200
    with TestClient(app) as staff:
        s=login(staff,'staff')
        assert staff.post(f'/api/tasks/{id}/submit',headers={'X-CSRF-Token':s},files={'file':('final.pdf',PDF,'application/pdf')}).status_code==201
    import app.taskflow as tf
    prior=tf.select_provider
    try:
        tf.select_provider=lambda db:None
        assert run_task_once()
    finally:tf.select_provider=prior
    row=client.get('/api/tasks').json()['items'][0]
    assert row['state']=='manual_review' and row['score'] is None
    assert client.post(f'/api/tasks/{id}/decide',headers={'X-CSRF-Token':h},json={'decision':'approved','note':'I manually inspected the PDF and confirm acceptance.'}).status_code==200
    assert client.get('/api/tasks').json()['items'][0]['state']=='approved'


def test_scoring_threshold_requires_actual_provider_and_no_uncertainty(client,login,monkeypatch):
    from app import taskflow as tf
    h=login(client,'hod');id=_batch(client,h,1)[0]
    rules=[{'id':f'rule{i}','title':f'Rule number {i}','type':'other','required':False,'value':'','instructions':'Check content'} for i in range(4)]
    r=client.post('/api/tasks/assign',headers={'X-CSRF-Token':h},json={'task_ids':[id],'staff_id':_staff_id(), 'notes':'Complete these four content requirements.', 'rules':rules})
    assert r.status_code==200,r.text
    monkeypatch.setattr(tf,'select_provider',lambda db:Provider('test','test-model','https://api.deepseek.com/chat/completions','unused'))
    from app.verification import Extracted
    monkeypatch.setattr('app.verification.extract_document',lambda *args:Extracted(['Doc content'],1,False,[]))
    def fake_ai(provider,system,payload,max_tokens=2200):
        return {'summary':'Reviewed','evaluations':[{'rule_id':f'rule{i}','result':('pass' if i<fake_ai.passed else 'issue'),'confidence':0.98,'evidence':'Document sample'} for i in range(4)]}
    monkeypatch.setattr(tf,'review_json',fake_ai)
    with TestClient(app) as staff:
        s=login(staff,'staff')
        for num,expected in [(3,'correction_required'),(4,'awaiting_hod')]:
            fake_ai.passed=num
            res=staff.post(f'/api/tasks/{id}/submit',headers={'X-CSRF-Token':s},files={'file':('completed.pdf',PDF,'application/pdf')})
            assert res.status_code==201,res.text
            assert run_task_once()
            item=staff.get('/api/tasks').json()['items'][0]
            assert item['score']==(75 if num==3 else 100)
            assert item['state']==expected


def test_insights_and_in_app_notifications_are_private(client,login):
    h=login(client,'hod');ids=_batch(client,h,2)
    summary=client.get('/api/tasks/insights/summary')
    assert summary.status_code==200 and summary.json()['total']==2
    with TestClient(app) as staff:
        login(staff,'staff')
        assert staff.get('/api/tasks/insights/summary').status_code==403
        assert staff.get('/api/tasks').json()['items']==[]
        assert staff.get('/api/tasks/notifications/inbox').json()['unread']==0
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/tasks').status_code==401
        assert anonymous.get('/tasks').status_code==401
        assert anonymous.get('/api/tasks/notifications/inbox').status_code==401
