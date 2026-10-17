"""Real Chromium screens, mock API transport; separate backend integration tests assert RBAC."""
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parents[1]/'static'

def test_browser():
  with sync_playwright() as pw:
    chrome=Path('/usr/bin/chromium')
    kw={'headless':True,'args':['--no-sandbox']}
    if chrome.exists():kw['executable_path']=str(chrome)
    browser=pw.chromium.launch(**kw)
    for role in ('hod','staff','principal','iqac','admin'):
      page=browser.new_page(viewport={'width':390 if role=='staff' else 1366,'height':840})
      errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
      html=(BASE/'tasks.html').read_text().replace('<link rel="stylesheet" href="/static/tasks.css">','<style>'+ (BASE/'tasks.css').read_text()+'</style>')
      html=html.replace('<script src="/static/tasks.js" defer></script>','')
      page.set_content(html)
      page.evaluate("""(role)=>{window.fetch=async(url,opts)=>{
        const u=String(url);let data={};
        if(u.includes('/auth/me'))data={user:{id:1,name:'Faculty Example',role,department:'Computer Applications'},csrf:'demo-token'};
        else if(u.endsWith('/tasks'))data={items:[{id:1,batch_id:1,file:'Academic_Audit.pdf',state:role==='hod'&&!window.__assigned?'unassigned':'assigned',department:'Computer Applications',assigned_to:'Faculty Example',assigned_staff_id:5,deadline:window.__changedDeadline||window.__assigned?.deadline||null,overdue:false,score:null,report:{},notes:'Please follow requirements',rules:[]}]};
        else if(u.endsWith('/staff'))data={items:[{id:5,name:'Faculty Example',username:'faculty',department:'Computer Applications'}]};
        else if(u.includes('/notifications/inbox'))data={unread:1,items:[{id:10,text:'Academic audit assigned',at:'2026-10-16T10:00:00Z',seen:false}]};
        else if(u.includes('/insights/summary'))data={staff:[],total:1,states:{assigned:1}};
        else if(u.includes('/insights/discussions'))data={items:[]};
        else if(u.includes('/ai/status'))data={configured:false,model:null};
        else if(u.endsWith('/tasks/rules/drafts'))data={items:[{task_id:1,state:'ready',summary:'Rules extracted from the uploaded PDF',model:'deepseek-chat',rules:[{id:'reference_1',title:'Introduction',type:'required_heading',required:true,value:'Introduction',instructions:'Use the introduction heading'}]}]};
        else if(u.endsWith('/tasks/assign')){window.__assigned=JSON.parse(opts.body);data={assigned:1};}
        else if(u.includes('/deadline')){window.__changedDeadline=JSON.parse(opts.body).deadline;data={changed:true,deadline:window.__changedDeadline};}
        else data={ok:true,assigned:1};
        return {ok:true,json:async()=>data,status:200};
      }}""",role)
      page.add_script_tag(content=(BASE/'tasks.js').read_text())
      page.get_by_text('Academic_Audit.pdf').wait_for()
      assert page.get_by_text('Academic audit assigned').count()==1
      if role=='hod':
        assert page.locator('#hod-section').is_visible()
        page.locator('[data-select="1"]').check()
        assert '1 unassigned PDFs selected' in page.locator('#selected-ids').inner_text()
        page.get_by_text('Rules extracted from the uploaded PDF').wait_for()
        assert page.locator('#rules').count()==0, 'Legacy line-by-line rule parser must be removed'
        assert page.locator('#review-confirm').is_enabled()
        page.locator('#staff-id').select_option('5')
        page.locator('#notes').fill('Complete the academic document following the reference PDF.')
        page.locator('#review-confirm').check()
        page.locator('#assign-form button[type=submit]').click()
        page.wait_for_function('window.__assigned && window.__assigned.use_generated_rules===true')
        data=page.evaluate('window.__assigned')
        assert data['confirmed_task_ids']==[1]
        assert data['task_ids']==[1]
      else:assert page.locator('#hod-section').is_hidden()
      if role=='staff':assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
      assert not errors,errors
      page.close()
    browser.close()
if __name__=='__main__':test_browser();print('TASK UI PASS: five roles and mobile')
