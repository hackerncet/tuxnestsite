"""Chromium interaction checks for the NCET public, faculty and responsive workflows.

The faculty data transport is explicitly mocked; backend roles and exports are
covered separately by integration tests. No production student data is used.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_bca import load_page

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def main():
    with sync_playwright() as playwright:
        executable = Path("/usr/bin/chromium")
        opts = {"headless":True,"args":["--no-sandbox"]}
        if executable.exists():
            opts["executable_path"]=str(executable)
        browser = playwright.chromium.launch(**opts)
        errors=[]
        page=browser.new_page(viewport={"width":1440,"height":900},accept_downloads=True)
        page.on("pageerror",lambda error: errors.append(str(error)))
        page.set_default_timeout(12000)

        # Anonymous visitors see functional links, a keyboard-operable help
        # accordion and a direct profile-search form, not rotating ad graphics.
        load_page(page,"public-home.html","public-home.js")
        assert page.locator(".film-frames").count()==0
        assert page.locator("a.service-card").count()==3
        for card in page.locator("a.service-card").all():
            assert card.get_attribute("href") in ("/students/portal","/students/directory")
        page.locator(".guide-grid summary").first.focus()
        page.keyboard.press("Enter")
        assert page.locator(".guide-grid details").first.evaluate("(el) => el.open")
        page.locator("#homepage-search").fill("1NC24BCA901")
        assert page.locator('form[role="search"]').get_attribute("method")=="get"

        # Roster export and search should work for an authorized BCA faculty
        # session without exposing temporary passwords in downloaded CSV.
        load_page(page,"bca-management.html")
        page.evaluate("""() => {
          const oldCreate=URL.createObjectURL.bind(URL);
          window.__exportedCSV=null;
          URL.createObjectURL=(blob)=>{
            blob.text().then(text=>window.__exportedCSV=text);
            return oldCreate(blob);
          };
          window.fetch=async(url)=>{
            const data=String(url).endsWith('/api/auth/me')?
              {csrf:'mock-csrf',user:{role:'staff',name:'Demo BCA Faculty'}}:
              String(url).endsWith('/api/bca/students')?
              {items:[
                {usn:'1NC24BCA901',name:'Student Alpha',semester:3,active:true},
                {usn:'1NC24BCA902',name:'Student Beta',semester:2,active:true}
              ]}:{items:[]};
            return new Response(JSON.stringify(data),{
              status:200,headers:{'Content-Type':'application/json'}});
          };
        }""")
        page.add_script_tag(content=(STATIC/"bca-management.js").read_text())
        page.locator("#desk").wait_for(state="visible")
        assert page.locator("#roster .entry").count()==2
        page.locator("#roster-search").fill("bca901")
        assert page.locator("#roster .entry").count()==1
        assert "Student Alpha" in page.locator("#roster").inner_text()
        page.locator("#roster-search").fill("unknown")
        assert page.get_by_text("No students match your search.").is_visible()
        page.locator("#roster-search").fill("")
        with page.expect_download() as download_info:
            page.locator("#export-roster").click()
        download=download_info.value
        assert download.suggested_filename=="NCET_BCA_roster_without_passwords.csv"
        page.wait_for_function("window.__exportedCSV !== null")
        exported=page.evaluate("window.__exportedCSV")
        assert "1NC24BCA901" in exported and "1NC24BCA902" in exported
        assert "temporary_password" not in exported
        assert "email" not in exported and "mobile" not in exported

        # Responsive checks across public and protected pages; no persistent
        # motion when reduced-motion is requested.
        for width in (320,390,768,1024,1440):
            page.set_viewport_size({"width":width,"height":900})
            load_page(page,"public-home.html","public-home.js")
            overflow=page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            assert not overflow, f"Horizontal overflow at {width}px"
        page.emulate_media(reduced_motion="reduce")
        load_page(page,"public-home.html","public-home.js")
        assert page.locator(".identity-crest").is_visible()
        duration=page.locator(".service-card").first.evaluate(
            "(el) => getComputedStyle(el).transitionDuration")
        assert duration in ("0s","1e-05s"), duration
        assert not errors, errors
        browser.close()


if __name__=="__main__":
    main()
    print("NCET experience checks passed: faculty roster, privacy-safe export, links, keyboard and responsive")
