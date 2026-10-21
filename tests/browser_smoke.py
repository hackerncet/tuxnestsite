"""Run with: python tests/browser_smoke.py (uses temporary test-only DB and port)."""
import os,subprocess,time,tempfile,signal,sys,urllib.request,urllib.error,secrets
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import launch_chromium
root=Path(__file__).parents[1]
with tempfile.TemporaryDirectory() as td:
 test_password=secrets.token_urlsafe(32)
 env=os.environ.copy()
 env.update({'PYTHONPATH':str(root),'DATABASE_URL':'sqlite:///'+str(Path(td)/'test.sqlite3'),
             'NCET_BOOTSTRAP_ADMIN_PASSWORD':test_password,
             'NCET_BOOTSTRAP_STAFF_PASSWORD':test_password,
             'NCET_BOOTSTRAP_HOD_PASSWORD':test_password,
             'NCET_BOOTSTRAP_PRINCIPAL_PASSWORD':test_password,
             'NCET_BOOTSTRAP_IQAC_PASSWORD':test_password,
             'PUBLIC_ORIGIN':'http://127.0.0.1:8778','NCET_BASE_URL':'http://127.0.0.1:8778',
             'APP_ENV':'development'})
 os.environ.update(env);sys.path.insert(0,str(root))
 from app.database import DBSession,Document,engine
 subprocess.check_call([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env,stdout=subprocess.DEVNULL)
 subprocess.check_call([sys.executable,'-m','app.bootstrap'],cwd=root,env=env,stdout=subprocess.DEVNULL)
 log_path=Path(td)/'uvicorn.log'
 with log_path.open('w',encoding='utf-8') as log:
  server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8778'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
 try:
  ready=False
  for _ in range(60):
   if server.poll() is not None:break
   try:
    with urllib.request.urlopen('http://127.0.0.1:8778/healthz',timeout=1) as response:
     ready=response.status==200
    if ready:break
   except (OSError,urllib.error.URLError):time.sleep(.25)
  if not ready:
   raise RuntimeError('Temporary browser test server did not become ready:\n'+log_path.read_text(encoding='utf-8',errors='replace'))
  with sync_playwright() as p:
   browser=launch_chromium(p,headless=True)
   context=browser.new_context(viewport={'width':1440,'height':900},accept_downloads=True)
   page=context.new_page();page.set_default_timeout(7000);errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   def signin(username):
    page.locator('#login-user').fill(username)
    page.locator('#login-pass').fill(test_password)
    page.locator('#login-form button[type=submit]').click()
    page.locator('.sidebar-brand').wait_for()
   page.goto('http://127.0.0.1:8778/app')
   assert page.get_by_text('Welcome to NCET VerifyFlow').is_visible()
   page.screenshot(path=str(Path(td)/'login.png'),full_page=True)
   signin('staff')
   assert page.get_by_text('Faculty submissions').is_visible()
   page.locator('[data-page=upload]').first.click()
   page.locator('#doc-title').fill('End-to-end browser document')
   page.locator('#doc-category').select_option('Academic Audit')
   page.locator('#doc-desc').fill('A full end to end security tested document to be reviewed.')
   page.locator('#file-input').set_input_files({'name':'audit.pdf','mimeType':'application/pdf','buffer':b'%PDF-1.7\nValid enough for signature test\n%%EOF'})
   page.locator('#submit-document button[type=submit]').click()
   page.get_by_text('End-to-end browser document').first.wait_for()
   page.screenshot(path=str(Path(td)/'staff.png'),full_page=True)
   # This standalone harness does not start the background verifier. Put only
   # this temporary document into the HOD's manual-review queue so the browser
   # can exercise the real role-gated decision flow without calling any AI API.
   with DBSession() as db:
    test_doc=db.query(Document).filter_by(title='End-to-end browser document').one()
    test_doc.status='manual_review';db.commit()
   page.locator('[data-action=logout]').click()
   signin('hod')
   page.locator('[data-page=documents]').first.click()
   page.get_by_text('End-to-end browser document').first.wait_for()
   page.locator('[data-open]').first.click()
   page.locator('[data-action=review][data-decision=approved]').click()
   page.locator('#review-note').fill('Reviewed and approved by HOD.')
   page.locator('#review-form button[type=submit]').click()
   page.get_by_text('Document approved',exact=True).first.wait_for()
   page.screenshot(path=str(Path(td)/'hod.png'),full_page=True)
   page.locator('[data-action=logout]').click()
   signin('principal')
   page.locator('[data-page=documents]').first.click()
   page.get_by_text('End-to-end browser document').first.wait_for()
   page.screenshot(path=str(Path(td)/'principal.png'),full_page=True)
   page.locator('[data-action=logout]').click()
   signin('admin')
   page.locator('[data-page=users]').first.click()
   page.get_by_text('Provisioned accounts').wait_for()
   page.locator('[data-page=audit]').first.click()
   page.get_by_text('Security audit',exact=True).first.wait_for()
   page.locator('[data-action=logout]').click()
   signin('iqac')
   page.locator('[data-page=documents]').first.click()
   page.get_by_text('End-to-end browser document').first.wait_for()
   mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
   mp=mobile.new_page();mp.goto('http://127.0.0.1:8778/app')
   mp.get_by_text('Welcome to NCET VerifyFlow').wait_for()
   mp.screenshot(path=str(Path(td)/'mobile.png'),full_page=True)
   print('BROWSER WORKFLOW PASSED | JS ERRORS:',errors)
   assert not errors,errors
   browser.close()
  subprocess.check_call([sys.executable,str(root/'tests'/'browser_responsive_audit.py')],cwd=root,env=env)
  subprocess.check_call([sys.executable,str(root/'tests'/'browser_institutional_motion.py')],cwd=root,env=env)
  subprocess.check_call([sys.executable,str(root/'tests'/'browser_not_found.py')],cwd=root,env=env)
 finally:
  server.terminate();server.wait(timeout=10);engine.dispose()
