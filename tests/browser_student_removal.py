"""Browser-only removal workflow; tests native UI against mocked backend transport."""
from pathlib import Path
from playwright.sync_api import sync_playwright

STATIC=Path(__file__).resolve().parents[1]/'static'
MOCK=r"""() => {
  window.__students=[
   {usn:'1NC24BCA001',name:'Student One',branch:'Computer Applications',semester:3,active:true},
   {usn:'1NC24BCA002',name:'Student Two',branch:'Computer Applications',semester:4,active:true},
   {usn:'1NC24BCA003',name:'Student Three',branch:'Computer Applications',semester:2,active:true}
  ];
  window.__removals=[];
  window.fetch=async(url,options={})=>{
   const u=String(url),payload=options.body&&options.headers?.['Content-Type']==='application/json'?JSON.parse(options.body):{};
   let data={},status=200;
   if(u==='/api/auth/me')data={user:{role:'admin',name:'Administrator',department:'Institution'},csrf:'csrf-example'};
   else if(u==='/api/bca/students')data={items:window.__students.map(x=>({...x}))};
   else if(u==='/api/academic/departments')data={items:[{code:'Computer Applications',name:'Computer Applications',active:true}]};
   else if(u==='/api/bca/students/removal/preview'){
     data={mode:payload.mode,count:payload.usns.length,items:payload.usns.map(usn=>({
       ...window.__students.find(x=>x.usn===usn),published:false,deletion_blockers:[]
     })),blocked:0,confirmation:(payload.mode==='delete'?'DELETE':'REMOVE')+' '+payload.usns.length+' STUDENTS',
      preview_token:'signed-token-example-very-long',note:'Test-only preview',requires_backup:payload.mode==='delete'};
   }else if(u==='/api/bca/students/removal/execute'){
      window.__removals.push(payload);
      if(payload.confirmation!==(payload.mode==='delete'?'DELETE':'REMOVE')+' '+payload.usns.length+' STUDENTS'){
        status=422;data={detail:'Mismatched confirmation'};
      }else{
        window.__students.forEach(x=>{if(payload.usns.includes(x.usn))x.active=false});
        data={action:payload.mode,affected:payload.usns.length};
      }
   }else if(u.startsWith('/api/bca/students'))data={items:window.__students};
   else {data={items:[]}};
   return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
  }
}"""


def audit():
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
  for width in (320,390,768,1366):
   page=browser.new_page(viewport={'width':width,'height':900})
   errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   html=(STATIC/'bca-management.html').read_text()
   for css in ('bca.css','department-management.css','student-removal.css'):
    if (STATIC/css).exists():
     import re
     html=re.sub(r'<link rel="stylesheet" href="/static/'+css.replace('.','\\.')+r'(?:\?v=[^"]+)?"\s*/?>',
        lambda m:'<style>'+(STATIC/css).read_text()+'</style>',html)
   import re
   html=re.sub(r'<script src="/static/bca-management.js(?:\?v=[^"]+)?" defer></script>','',html)
   page.set_content(html)
   page.evaluate(MOCK)
   page.add_script_tag(content=(STATIC/'bca-management.js').read_text())
   page.locator('#roster .select-student').first.wait_for()
   assert page.locator('#roster .select-student').count()==3
   page.locator('#select-visible-students').click()
   assert page.locator('#selected-student-count').inner_text()=='3 selected'
   page.locator('#clear-student-selection').click()
   assert page.locator('#selected-student-count').inner_text()=='0 selected'
   page.locator('#roster .select-student').first.check()
   page.locator('#review-student-removal').click()
   page.locator('#student-removal-review').wait_for(state='visible')
   assert page.locator('#removal-phrase').inner_text()=='REMOVE 1 STUDENTS'
   assert page.locator('#removal-backup-label').is_hidden()
   page.locator('#student-removal-confirm-form [name=reason]').fill('This duplicate needs to be removed.')
   page.locator('#student-removal-confirm-form [name=confirmation]').fill('REMOVE 1 STUDENTS')
   page.locator('#student-removal-confirm-form [name=current_password]').fill('TestPassword-12345!')
   page.locator('#execute-student-removal').click()
   page.wait_for_function('window.__removals.length===1')
   page.get_by_text('1 student accounts disabled',exact=False).wait_for()
   assert page.locator('#selected-student-count').inner_text()=='0 selected'
   assert page.locator('#roster .select-student').count()==2
   page.locator('#show-disabled-students').check()
   assert page.locator('#roster .select-student').count()==3
   assert not errors,errors
   assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 3'),width
   page.close()
  browser.close()
 print('STUDENT REMOVAL UI PASS: selected group, preview, confirmation, revoke, mobile screens')

if __name__=='__main__':audit()
