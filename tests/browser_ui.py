"""Frontend-only browser smoke with deterministic mock responses (real API is separately tested)."""
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).parents[1]
MOCK=r'''() => {
  const users=['admin','hod','staff','principal','iqac'];
  let signed=null;let csrf='fake_csrf';let rulebook={version:0,rules:[],history:[]};let docs=[];
  const now=()=>new Date().toISOString();
  window.fetch=async(url,opts={})=>{
    const path=String(url),method=opts.method||'GET';let response={ok:true},status=200;
    if(path==='/api/auth/me'){if(!signed){status=401;response={detail:'Please sign in'};}else response={user:{role:signed,name:'NCET '+signed,department:'Computer Science & Engineering',username:signed,id:users.indexOf(signed)+1},csrf};}
    else if(path==='/api/auth/login'){
      const req=JSON.parse(opts.body);if(!users.includes(req.username)||req.username!==req.role){status=401;response={detail:'Invalid credentials'};}
      else{signed=req.username;response={user:{role:signed,name:'NCET '+signed,department:'Computer Science & Engineering',username:signed,id:users.indexOf(signed)+1},csrf};}
    }else if(path==='/api/auth/logout'){signed=null;}
    else if(path.startsWith('/api/documents?')){const view=docs.filter(d=>signed==='staff'||signed==='hod'||d.status==='approved');response={items:view,total:view.length};}
    else if(path==='/api/documents'&&method==='POST'){const form=opts.body,file=form.get('file');docs.push({id:'NCET-2026-BROWSER',title:form.get('title'),category:form.get('category'),year:form.get('year'),description:form.get('description'),department:'Computer Science & Engineering',status:'verifying',version:1,submitted:now(),author:'NCET staff',fileName:file.name,fileSize:file.size,hasLocalFile:true,history:[{kind:'submitted',note:'Verification queued',at:now(),by:'NCET staff'}],verification:{status:'queued',revision:1}});}
    else if(path==='/api/rules'){if(method==='PUT'){const b=JSON.parse(opts.body);rulebook={version:rulebook.version+1,rules:b.rules,history:[{version:rulebook.version+1,created:now()}]};response={ok:true,version:rulebook.version};}else response=rulebook;}
    else if(path.endsWith('/verification')){const d=docs[0];response={document_id:d.id,revision:1,policy_version:rulebook.version,status:d.status,report:{status:'needs_correction',rule_count:1,page_count:1,ai_used:false,summary:'Manual check needed',findings:[{rule_id:'heading',title:'Executive Summary',result:'issue',source:'deterministic',location:'Page 1',issue:'Required heading not found',correction:'Add the heading',confidence:1}]}};}
    else if(path.endsWith('/review')&&method==='POST'){const b=JSON.parse(opts.body);docs[0].status=b.decision;docs[0].history.push({kind:b.decision,by:'NCET hod',note:b.note,at:now()});}
    else if(path.endsWith('/resubmit')&&method==='POST'){docs[0].version++;docs[0].status='manual_review';}
    else if(path==='/api/users'){response={items:users.map((u,i)=>({id:i+1,username:u,name:'NCET '+u,role:u,department:'Computer Science & Engineering',active:true}))};}
    else if(path==='/api/admin/integrations'){response={openrouter_configured:false,model:'google/gemma-4-31b-it:free'};}
    else if(path==='/api/audit'){response={items:[]};}
    else if(path==='/api/auth/change-password'){response={ok:true};}
    else{status=404;response={detail:'Unknown request: '+path};}
    return new Response(JSON.stringify(response),{status,headers:{'content-type':'application/json'}});
  };
}'''
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':900})
    page=context.new_page();page.set_default_timeout(11000)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content('<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1" /></head><body><div id="app"></div></body></html>')
    css=(ROOT/'static/styles.css').read_text()
    js=(ROOT/'static/app.js').read_text()
    for name in ('ncet-crest','ngi-logo'):
        suffix='ncet-crest.webp' if name=='ncet-crest' else 'ngi-logo.webp'
        data='data:image/webp;base64,'+base64.b64encode((ROOT/'static'/suffix).read_bytes()).decode()
        js=js.replace('/static/'+suffix,data)
    page.evaluate('(css)=>{const s=document.createElement("style");s.textContent=css;document.head.appendChild(s)}',css)
    page.evaluate(MOCK)
    page.add_script_tag(content=js)
    page.get_by_text('Welcome to your workspace.').wait_for()
    assert page.locator('.roles .role-option').count()==5
    page.screenshot(path=str(ROOT/'tests/ui-login.png'),full_page=True)
    def signin(u):
        page.locator(f'[data-action=pick-role][data-role={u}]').click()
        page.locator('#login-user').fill(u);page.locator('#login-pass').fill('test-pass')
        page.locator('#login-form button[type=submit]').click();page.locator('.sidebar-brand').wait_for()
    def signout():page.locator('[data-action=logout]').click();page.locator('#login-user').wait_for()
    signin('admin')
    page.locator('[data-page=users]').first.click();page.get_by_text('Provisioned accounts').wait_for()
    page.locator('[data-page=integrations]').first.click();page.get_by_text('AI model configuration').wait_for()
    page.screenshot(path=str(ROOT/'tests/ui-admin.png'),full_page=True)
    signout();signin('hod')
    page.locator('[data-page=rules]').first.click();page.locator('[data-action=add-rule]').click()
    page.locator('.rule-entry [name=title]').fill('Executive summary heading')
    page.locator('.rule-entry [name=value]').fill('Executive Summary')
    page.locator('#rule-form button[type=submit]').click();page.get_by_text('Version 1',exact=True).wait_for()
    page.screenshot(path=str(ROOT/'tests/ui-rules.png'),full_page=True)
    signout();signin('staff')
    page.locator('[data-page=upload]').first.click()
    page.locator('#doc-title').fill('NCET Annual Faculty Report')
    page.locator('#doc-category').select_option('Academic Audit')
    page.locator('#doc-desc').fill('Academic year department faculty annual documentation submission.')
    page.locator('#file-input').set_input_files({'name':'document.pdf','mimeType':'application/pdf','buffer':b'%PDF-1.7\nTEST ONLY\n%%EOF'})
    page.locator('#submit-document button[type=submit]').click()
    page.get_by_text('NCET Annual Faculty Report').first.wait_for()
    page.locator('[data-open]').first.click();page.locator('[data-action=verification]').click()
    page.get_by_text('Verification report',exact=True).first.wait_for()
    page.screenshot(path=str(ROOT/'tests/ui-report.png'),full_page=True)
    page.locator('[data-action=close-modal]').first.click()
    signout();signin('principal')
    assert page.locator('[data-page=users]').count()==0
    signout();signin('iqac')
    assert page.locator('[data-page=users]').count()==0
    mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    mp=mobile.new_page();mp.set_content('<html><meta name="viewport" content="width=device-width, initial-scale=1"/><body><div id="app"></div></body></html>')
    mp.evaluate('(css)=>{const s=document.createElement("style");s.textContent=css;document.head.appendChild(s)}',css)
    mp.evaluate(MOCK);mp.add_script_tag(content=js)
    mp.get_by_text('Welcome to your workspace.').wait_for()
    mp.screenshot(path=str(ROOT/'tests/ui-mobile.png'),full_page=True)
    assert not errors,errors
    print('UI SMOKE PASS: 5 roles, Super Admin, HOD rules, Staff upload, verification report, Principal/IQAC isolation, mobile. JS errors:',errors)
    browser.close()
