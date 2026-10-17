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
      html=html.replace('<script src="/static/hod-dashboard.js?v=20261017" defer></script>','')
      html=html.replace('<link rel="stylesheet" href="/static/hod-dashboard.css?v=20261017">',
        '<style>'+ (BASE/'hod-dashboard.css').read_text()+'</style>')
      page.set_content(html)
      page.evaluate("""(role)=>{window.fetch=async(url,opts)=>{
        const u=String(url);let data={};
        if(u.includes('/auth/me'))data={user:{id:1,name:'Faculty Example',role,department:'Computer Applications'},csrf:'demo-token'};
        else if(u.endsWith('/tasks'))data={items:[{id:1,batch_id:1,file:'Academic_Audit.pdf',state:role==='hod'&&!window.__assigned?'unassigned':'assigned',department:'Computer Applications',assigned_to:'Faculty Example',assigned_staff_id:5,deadline:window.__changedDeadline||window.__assigned?.deadline||null,overdue:false,score:null,report:{},notes:'Please follow requirements',rules:[]}]};
        else if(u.endsWith('/tasks/dashboard')){
          const assigned=Boolean(window.__assigned);
          const eventTime='2026-10-17T10:00:00+00:00';
          const history=assigned?[{event:'assigned',at:eventTime,actor:'NCET hod',detail:'Assigned to Faculty Example',state:'assigned'}]:[];
          data={counts:{total:1,working:assigned?1:0,reviewing:0,approved:0,overdue:0,unassigned:assigned?0:1},
            as_of:eventTime,daily_approvals:[],task_list_truncated:false,
            staff:assigned?[{id:5,name:'Faculty Example',total:1,working:1,reviewing:0,approved:0,overdue:0}]:[],
            activity:assigned?[{...history[0],task_id:1,file:'Academic_Audit.pdf',staff:'Faculty Example'}]:[],
            tasks:[{id:1,file:'Academic_Audit.pdf',staff:assigned?'Faculty Example':null,
              staff_id:assigned?5:null,state:assigned?'assigned':'unassigned',score:null,
              submitted_at:null,approved_at:null,deadline:window.__assigned?.deadline||null,
              updated_at:eventTime,overdue:false,history}]};
        }
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
      page.add_script_tag(content=(BASE/'hod-dashboard.js').read_text())
      page.add_script_tag(content=(BASE/'tasks.js').read_text())
      page.get_by_text('Academic_Audit.pdf').wait_for()
      assert page.get_by_text('Academic audit assigned').count()==1
      if role=='hod':
        assert page.locator('#hod-section').is_visible()
        assert page.locator('#hod-dashboard').is_visible()
        page.locator('#dashboard-metrics [data-dash-status="all"] strong').wait_for()
        assert page.locator('#dashboard-metrics [data-dash-status="all"] strong').inner_text()=='1'
        assert page.locator('#dashboard-metrics [data-dash-status="approved"] strong').inner_text()=='0'
        assert page.locator('#dash-stage-chart .stage-ring').is_visible()
        assert page.locator('#dash-trend-chart .daily-column').count()==14
        page.locator('[data-select="1"]').check()
        assert '1 unassigned PDFs selected' in page.locator('#selected-ids').inner_text()
        page.get_by_text('Rules extracted from the uploaded PDF').wait_for()
        assert page.locator('#rules').count()==0, 'Legacy line-by-line rule parser must be removed'
        assert page.locator('#review-confirm').is_enabled()
        page.locator('#staff-id').select_option('5')
        page.locator('#notes').fill('Complete the academic document following the reference PDF.')
        page.locator('#review-confirm').check()
        assert page.locator('#assignment-deadline[type="datetime-local"]').is_visible()
        date_value=page.evaluate("""() => {
          const d=new Date(Date.now()+3*86400000);
          const pad=n=>String(n).padStart(2,'0');
          return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+'T'+pad(d.getHours())+':'+pad(d.getMinutes());
        }""")
        page.locator('#assignment-deadline').fill(date_value)
        page.locator('#assign-form button[type=submit]').click()
        page.wait_for_function('window.__assigned && window.__assigned.use_generated_rules===true')
        data=page.evaluate('window.__assigned')
        assert data['confirmed_task_ids']==[1]
        assert data['task_ids']==[1]
        assert data['deadline'] and data['deadline'].startswith(date_value[:10])
        page.locator('button[data-op="deadline"]').wait_for(state='visible')
        page.locator('button[data-op="deadline"]').click()
        assert page.locator('#deadline-dialog').is_visible()
        page.locator('#edit-deadline').fill(date_value)
        page.locator('#deadline-form button[type=submit]').click()
        page.wait_for_function('window.__changedDeadline !== undefined')
        assert page.locator('#deadline-dialog').is_hidden()
        page.locator('#dashboard-metrics [data-dash-status="working"] strong').wait_for()
        page.locator('#dashboard-metrics [data-dash-status="working"]').click()
        assert page.locator('#dash-tasks .dashboard-task').count()==1
        page.locator('#dash-tasks .dashboard-task summary').click()
        assert page.locator('.dash-history').is_visible()
        assert 'NCET hod' in page.locator('.dash-history').inner_text()
        page.locator('#dash-search').fill('not-found-file')
        assert 'No matching tasks' in page.locator('#dash-tasks').inner_text()
        page.locator('#dash-search').fill('Academic_Audit')
        assert page.locator('.dashboard-task').count()==1

      else:
        assert page.locator('#hod-section').is_hidden()
        assert page.locator('#hod-dashboard').is_hidden()
      if role=='staff':
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
        assert page.locator('.deadline-cell').count()==1
        assert page.locator('button[data-op="deadline"]').count()==0
      assert not errors,errors
      page.close()
    browser.close()
if __name__=='__main__':test_browser();print('TASK UI PASS: five roles and mobile')
