"""Render a published NCET student résumé in Chromium at mobile/desktop widths."""
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

fd,path=tempfile.mkstemp(prefix='ncet-resume-',suffix='.sqlite3')
os.close(fd)
os.environ['APP_ENV']='development'
os.environ['DATABASE_URL']='sqlite:///'+path
os.environ['STORAGE_BACKEND']='database'
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from app.main import app
from app.database import Base,DBSession,engine,User
from app.student_models import BCAStudent
from app.student_profiles import StudentShowcase
from app.departments import AcademicDepartment

static=Path(__file__).resolve().parents[1]/'static'
Base.metadata.create_all(engine)
with DBSession() as db:
    db.add(AcademicDepartment(code='Computer Science & Engineering',name='Computer Science & Engineering',active=True))
    u=User(username='1nc24cs150',display_name='Example Engineering Student',
           role='student',department='Computer Science & Engineering',active=True,
           password_hash='not-used')
    db.add(u);db.flush()
    db.add(BCAStudent(user_id=u.id,usn='1NC24CS150',semester=5,must_change_password=False))
    db.add(StudentShowcase(student_id=u.id,published=True,
           about='Building useful campus tools and learning responsible engineering.',
           skills_json='["Python","C++","FastAPI"]',
           interests_json='["Artificial Intelligence","Open Source"]',
           projects_json='[{"title":"Student Project","description":"A campus workflow application","technologies":["Python","React"],"github_url":"https://github.com/example/demo","live_url":"https://example.org/demo"}]',
           certificates_json='[{"title":"Programming Certificate","issuer":"Cisco","proof_url":"https://example.org/cert"}]',
           social_links_json='{"github":"https://github.com/example"}'))
    db.commit()
with TestClient(app) as client:
    html=client.get('/students/profile/1NC24CS150').text
assert 'Student Project' in html and 'Programming Certificate' in html

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width in (320,375,390,768,1024,1440):
        page=browser.new_page(viewport={'width':width,'height':850},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        def serve(route):
            location=urlsplit(route.request.url).path
            if location.startswith('/static/'):
                file=(static/location[len('/static/'):]).resolve()
                if not file.is_relative_to(static.resolve()) or not file.exists():
                    route.fulfill(status=404,body='Not found');return
                suffix=file.suffix.lower()
                mime={'.png':'image/png','.css':'text/css','.js':'text/javascript','.webp':'image/webp'}.get(suffix,'application/octet-stream')
                route.fulfill(status=200,body=file.read_bytes(),headers={'content-type':mime})
            elif location=='/students/profile/1NC24CS150':
                route.fulfill(status=200,body=html,headers={'content-type':'text/html; charset=utf-8'})
            else:route.fulfill(status=404,body='Not found')
        page.route('http://ncet.test/**',serve)
        page.goto('http://ncet.test/students/profile/1NC24CS150',wait_until='load')
        report=page.evaluate("""() => ({
            width: document.documentElement.scrollWidth,viewport:innerWidth,
            sections:[...document.querySelectorAll('.resume-section')].map(x=>x.id),
            images:[...document.images].map(img=>({source:img.src,loaded:img.complete&&img.naturalWidth>0}))
        })""")
        assert report['width']<=width+2,(width,report)
        assert report['sections']==['about','skills','projects','certifications','interests','links']
        assert all(x['loaded'] for x in report['images']),(width,report['images'])
        assert not errors,(width,errors)
        page.close()
    browser.close()
os.unlink(path)
print('NCET résumé audit passed: six widths, six sections, all institutional images loaded.')
