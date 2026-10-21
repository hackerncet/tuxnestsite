"""Browser test: BCA student skill list and signed-in notification panel."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_runtime import launch_chromium
from browser_bca import load_page

STATIC=Path(__file__).resolve().parents[1]/'static'

def main():
    with sync_playwright() as pw:
        browser=launch_chromium(pw,headless=True)
        page=browser.new_page(viewport={'width':390,'height':844})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        load_page(page,'student-portal.html','student-portal.js',mock_denied=True)
        page.evaluate("""() => {
          const input=document.getElementById('showcase-skills');
          input.value=Array.from({length:50},(_,i)=>i===0?'C':'Skill '+i).join(', ');
          input.dispatchEvent(new Event('input',{bubbles:true}));
        }""")
        assert '50 / 100' in page.locator('#skill-count').inner_text()
        assert page.locator('#showcase-skills').evaluate('(e)=>e.tagName')=='TEXTAREA'
        assert page.locator('.social-link').count()>=9
        page.goto('about:blank')
        page.set_content('<main><h1>Logged-in NCET dashboard</h1><p id="notification-status"></p><section id="notification-page-items"></section><button id="notification-refresh">Refresh</button></main>')
        page.evaluate("""() => {
          window.inboxRequests=0;
          window.fetch=async url=>{
            if(String(url).includes('/api/auth/me'))
              return new Response(JSON.stringify({csrf:'mock-token',user:{role:'principal'}}),{status:200,headers:{'Content-Type':'application/json'}});
            if(String(url).includes('/api/alerts/inbox')){
              window.inboxRequests++;
              return new Response(JSON.stringify({unread:2,items:[
                {id:'a-1',text:'New BCA student request',category:'complaints',link:'/bca/oversight',seen:false,at:'2026-10-16T10:00:00+00:00'},
                {id:'t-1',text:'A task was assigned',category:'tasks',link:'/tasks',seen:false,at:'2026-10-16T11:00:00+00:00'}
              ]}),{status:200,headers:{'Content-Type':'application/json'}});
            }
            return new Response('{}',{status:200});
          };
        }""")
        page.add_script_tag(content=(STATIC/'notifications-page.js').read_text(encoding='utf-8'))
        page.add_script_tag(content=(STATIC/'notifications.js').read_text(encoding='utf-8'))
        page.locator('#ncet-alerts').wait_for(state='visible')
        assert '2 new' in page.locator('#alert-count').inner_text()
        page.locator('#alert-toggle').click()
        assert page.locator('.alert-entry').count()==2
        assert page.locator('#alert-list a[href="/bca/oversight"]').count()==1
        assert page.locator('.notification-card').count()==2
        assert page.locator('.alert-inbox-link').get_attribute('href')=='/notifications'
        page.wait_for_function('window.inboxRequests >= 2',timeout=3500)
        assert 'Updates automatically every 1.5 seconds' in page.locator('#notification-status').inner_text()
        page.keyboard.press('Escape')
        assert page.locator('#alert-list').is_hidden()
        assert errors==[],errors
        browser.close()

def test_slow_notification_inbox_response_is_not_cancelled_at_poll_interval():
    with sync_playwright() as pw:
        browser=launch_chromium(pw,headless=True)
        page=browser.new_page(viewport={'width':390,'height':844})
        page.set_content('<main>NCET</main>')
        page.evaluate("""() => {
          window.slowAbortCount=0;
          window.fetch=async (url,options={})=>{
            if(!String(url).includes('/api/alerts/inbox'))
              return new Response('{}',{status:200});
            return await new Promise((resolve,reject)=>{
              const signal=options.signal;
              const abort=()=>{window.slowAbortCount++;reject(new DOMException('Aborted','AbortError'));};
              signal?.addEventListener('abort',abort,{once:true});
              setTimeout(()=>{
                signal?.removeEventListener('abort',abort);
                resolve(new Response(JSON.stringify({
                  unread:1,csrf:'slow-token',items:[{
                    id:'a-77',text:'Slow response delivered',category:'tasks',
                    link:'/tasks',seen:false,at:'2026-10-21T10:00:00+00:00'
                  }]
                }),{status:200,headers:{'Content-Type':'application/json'}}));
              },1800);
            });
          };
        }""")
        page.add_script_tag(content=(STATIC/'notifications.js').read_text(encoding='utf-8'))
        page.locator('#alert-count').wait_for(state='visible')
        page.wait_for_function("document.querySelector('#alert-count').textContent.includes('1 new')",timeout=5000)
        assert 'Slow response delivered' in page.locator('#alert-items').inner_text()
        assert page.evaluate('window.slowAbortCount')==0
        browser.close()


if __name__=='__main__':
    main()
    test_slow_notification_inbox_response_is_not_cancelled_at_poll_interval()
    print('Skill and notification Chromium smoke tests passed')
