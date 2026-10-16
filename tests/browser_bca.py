"""Chromium smoke checks for BCA public/student/member-only pages.

UI checks use static resources with mocked API responses. Authorization is
tested separately in FastAPI integration tests; no real production accounts used.
"""
from pathlib import Path
import base64
import re
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'static'


def load_page(page, html_file, script=None, mock_denied=False):
    html = (STATIC / html_file).read_text(encoding='utf-8')
    for asset in ('ncms-emblem.webp', 'ngi-logo.webp'):
        image = STATIC / asset
        if image.is_file():
            uri = 'data:image/webp;base64,' + base64.b64encode(image.read_bytes()).decode()
            html = html.replace('/static/' + asset, uri)
    for css in ('bca.css', 'community.css'):
        html = html.replace('<link rel="stylesheet" href="/static/' + css + '">',
                            '<style>' + (STATIC / css).read_text(encoding='utf-8') + '</style>')
    html = re.sub(r'<script src="/static/[^"]+" defer></script>', '', html)
    page.set_content(html, wait_until='load')
    if mock_denied:
        page.evaluate("""() => {
          window.fetch = async (url) => new Response(
            JSON.stringify({detail: 'Not authorized'}),
            {status:401, headers:{'Content-Type':'application/json'}}
          );
        }""")
    if script:
        page.add_script_tag(content=(STATIC / script).read_text(encoding='utf-8'))


def main():
    with sync_playwright() as pw:
        binary = Path('/usr/bin/chromium')
        opts = {'headless':True,'args':['--no-sandbox']}
        if binary.is_file():
            opts['executable_path'] = str(binary)
        browser = pw.chromium.launch(**opts)
        errors = []
        desktop = browser.new_page(viewport={'width':1440,'height':900})
        desktop.on('pageerror', lambda e: errors.append(str(e)))
        desktop.set_default_timeout(8000)

        load_page(desktop, 'public-home.html', 'public-home.js')
        assert desktop.locator('h1').inner_text().startswith('College services.')
        assert desktop.locator('.logo-stage img').evaluate('(img) => img.naturalWidth') > 0
        desktop.locator('#toggle-animation').click()
        assert desktop.locator('#logo-stage.paused').count() == 1
        assert desktop.locator('a[href="/students"]').count() > 0

        load_page(desktop, 'student-services.html')
        assert 'BACHELOR OF COMPUTER APPLICATIONS' in desktop.locator('main').inner_text().upper()
        assert desktop.locator('a[href="/students/portal"]').count() > 0

        load_page(desktop, 'student-portal.html','student-portal.js',mock_denied=True)
        desktop.locator('#login-usn').fill('1NC24BCA001')
        desktop.locator('#login-password').fill('incorrect-pass')
        desktop.locator('#login-form button[type=submit]').click()
        desktop.get_by_text('Not authorized').first.wait_for()
        assert desktop.locator('#login-password').input_value() == ''

        load_page(desktop, 'bca-management.html','bca-management.js',mock_denied=True)
        desktop.locator('#denied').wait_for(state='visible')

        load_page(desktop,'community.html','community.js',mock_denied=True)
        desktop.get_by_text('Sign in required').first.wait_for()
        assert errors == [], errors

        mobile = browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
        mobile.on('pageerror', lambda e: errors.append(str(e)))
        for name in ('public-home.html','student-services.html'):
            load_page(mobile,name)
            assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'),name
        browser.close()
        assert errors == [], errors


if __name__ == '__main__':
    main()
    print('BCA Chromium smoke checks passed: public pages, logo animation, private access, mobile')
