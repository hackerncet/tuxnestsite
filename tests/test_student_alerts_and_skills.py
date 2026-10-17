"""BCA skill capacity, public link validation, request alerts and role-scoped oversight."""
from fastapi.testclient import TestClient
from app.main import app
from app.database import DBSession, User

def make_bca_hod():
    with DBSession() as db:
        hod=db.query(User).filter_by(username='hod').one()
        hod.department='Computer Applications'
        db.commit()

def create_student(client,login,suffix='701'):
    make_bca_hod()
    csrf=login(client,'hod')
    resp=client.post('/api/bca/students/enroll',headers={'X-CSRF-Token':csrf},
        json={'students':[{'usn':'1NC24BCA'+suffix,'full_name':'Student Example','semester':3}]})
    assert resp.status_code==200,resp.text
    return resp.json()['credentials'][0]['temporary_password']

def sign_in_student(client,suffix,password):
    response=client.post('/api/auth/login',json={
        'username':'1nc24bca'+suffix,'password':password,'role':'student'})
    assert response.status_code==200,response.text
    csrf=response.json()['csrf']
    changed=client.post('/api/auth/change-password',headers={'X-CSRF-Token':csrf},
        json={'old_password':password,'new_password':'ChangedStudentPassword12345!'})
    assert changed.status_code==200,changed.text
    return csrf

def test_48_skills_c_single_letter_and_social_profiles(client,login):
    password=create_student(client,login)
    skills=['Python','Java','C','C++','JavaScript','TypeScript','SQL','HTML5','CSS3','React.js',
       'Node.js','Express.js','Flask','FastAPI','REST APIs','Machine Learning','Deep Learning',
       'Generative AI','Large Language Models (LLMs)','Natural Language Processing (NLP)',
       'Prompt Engineering','Retrieval-Augmented Generation (RAG)','AI Agents','LangChain',
       'LangGraph','Model Context Protocol (MCP)','Transformers','Hugging Face','Ollama',
       'PyTorch','TensorFlow','Scikit-learn','NumPy','Pandas','Matplotlib','Data Preprocessing',
       'Feature Engineering','Model Training','Model Evaluation','Classification Algorithms',
       'Decision Trees','Random Forest','Support Vector Machines (SVM)','Neural Networks',
       'Embeddings','Vector Databases','Semantic Search','LLM Fine','R']
    with TestClient(app) as student:
        csrf=sign_in_student(student,'701',password)
        payload={'full_name':'Student Example','skills':skills,'publish':True,
            'social_links':{'github':'https://github.com/example','linkedin':'https://www.linkedin.com/in/example/',
                'leetcode':'https://leetcode.com/u/example/','codechef':'https://www.codechef.com/users/example'},
            'mobile':'+919876543210','email':'student.private@example.org',
            'about':'Developing AI tools','certificates':[]}
        saved=student.put('/api/bca/showcase/me',headers={'X-CSRF-Token':csrf},json=payload)
        assert saved.status_code==200,saved.text
        assert student.get('/api/bca/showcase/me').json()['skills']==skills
        invalid=student.put('/api/bca/showcase/me',headers={'X-CSRF-Token':csrf},
              json={**payload,'social_links':{'github':'https://wrong.example/my-github'}})
        assert invalid.status_code==422
    public=client.get('/api/bca/directory/1NC24BCA701')
    assert public.status_code==200
    assert public.json()['skills']==skills
    page=client.get('/students/profile/1NC24BCA701')
    assert 'https://github.com/example' in page.text
    assert 'https://www.linkedin.com/in/example/' in page.text
    for response in (public.text,page.text,client.get('/api/bca/directory').text):
        assert '9876543210' not in response
        assert 'student.private@example.org' not in response

def test_complaint_notification_principal_summary_and_project_alert(client,login):
    password=create_student(client,login,'702')
    with TestClient(app) as student:
        csrf=sign_in_student(student,'702',password)
        resp=student.post('/api/bca/cases',headers={'X-CSRF-Token':csrf},json={
            'category':'academics','subject':'Class scheduling concern','description':'Please review the change in class schedule for our semester.'})
        assert resp.status_code==201,resp.text
        ref=resp.json()['reference']
        assert 'NCET-BCA-' in ref
        assert student.get('/api/alerts/inbox').json()['unread']==0
        with TestClient(app) as hod:
            h=login(hod,'hod')
            inbox=hod.get('/api/alerts/inbox').json()
            complaints=[n for n in inbox['items'] if n['category']=='complaints']
            assert len(complaints)==1
            assert complaints[0]['link']=='/bca/manage'
            mark=hod.post('/api/alerts/'+complaints[0]['id']+'/read',headers={'X-CSRF-Token':h})
            assert mark.status_code==200
            assert hod.get('/api/alerts/inbox').json()['unread']==0
            response=hod.post('/api/bca/cases/'+ref+'/messages',headers={'X-CSRF-Token':h},
                json={'message':'Please share the exact schedule details.'})
            assert response.status_code==200,response.text
            summary=hod.get('/api/bca/oversight')
            assert summary.status_code==200
            assert summary.json()['cases_total']==1
            assert summary.json()['cases'][0]['subject']=='Class scheduling concern'
        updated=student.get('/api/alerts/inbox').json()
        assert any(n['category']=='complaints' for n in updated['items'])
        post=student.post('/api/community/posts',headers={'X-CSRF-Token':csrf},
            json={'title':'Building a campus assistant','description':'We are developing a web project to support academic resources for BCA students.',
                  'help_needed':'Frontend collaboration for our project'})
        assert post.status_code==201,post.text
    with TestClient(app) as principal:
        login(principal,'principal')
        data=principal.get('/api/bca/oversight').json()
        assert data['cases_total']==1
        assert data['projects_total']==1
        assert 'cases' not in data
        assert 'Class scheduling concern' not in str(data)
        assert principal.get('/api/bca/cases/'+ref).status_code==403
        assert any(n['category']=='projects' for n in principal.get('/api/alerts/inbox').json()['items'])
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/alerts/inbox').status_code==401
        assert anonymous.get('/bca/oversight').status_code==401
