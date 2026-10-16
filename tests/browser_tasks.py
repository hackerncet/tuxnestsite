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
        else if(u.endsWith('/tasks'))data={items:[{id:1,batch_id:1,file:'Academic_Audit.pdf',state:role==='hod'?'unassigned':'assigned',department:'Computer Applications',assigned_to:'Faculty Example',score:null,report:{},notes:'Please follow requirements',rules:[]}]};
        else if(u.endsWith('/staff'))data={items:[{id:5,name:'Faculty Example',username:'faculty',department:'Computer Applications'}]};
        else if(u.includes('/notifications/inbox'))data={unread:1,items:[{id:10,text:'Academic audit assigned',at:'2026-10-16T10:00:00Z',seen:false}]};
        else if(u.includes('/insights/summary'))data={staff:[],total:1,states:{assigned:1}};
        else if(u.includes('/insights/discussions'))data={items:[]};
        else if(u.includes('/ai/status'))data={configured:false,model:null};
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
      else:assert page.locator('#hod-section').is_hidden()
      if role=='staff':assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
      assert not errors,errors
      page.close()
    browser.close()
if __name__=='__main__':test_browser();print('TASK UI PASS: five roles and mobile')
