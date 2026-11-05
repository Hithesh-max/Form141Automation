import asyncio
import json
from playwright.async_api import async_playwright

PORTAL_URL = "https://eportal.incometax.gov.in/iec/foservices/#/login"

JS_CAPTURE = """() => {
    const info = {
        url: window.location.href,
        title: document.title,
        inputs: [],
        buttons: [],
        selects: []
    };
    document.querySelectorAll('input').forEach(el => {
        info.inputs.push({
            id: el.id,
            name: el.name,
            type: el.type,
            placeholder: el.placeholder,
            formControl: el.getAttribute('formcontrolname'),
            ariaLabel: el.getAttribute('aria-label'),
            ngModel: el.getAttribute('ng-model'),
            visible: el.offsetParent !== null
        });
    });
    document.querySelectorAll('button, [role="button"], input[type="submit"]').forEach(el => {
        info.buttons.push({
            id: el.id,
            text: (el.innerText || '').trim().substring(0, 100),
            cls: el.className.substring(0, 100),
            visible: el.offsetParent !== null
        });
    });
    document.querySelectorAll('select, mat-select, ng-select, p-dropdown').forEach(el => {
        info.selects.push({
            tag: el.tagName,
            id: el.id,
            formControl: el.getAttribute('formcontrolname'),
            name: el.getAttribute('name')
        });
    });
    return info;
}"""


async def capture(page, label):
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    await asyncio.sleep(3)

    result = await page.evaluate(JS_CAPTURE)

    print(f"\n{'=' * 70}")
    print(f"  STEP : {label}")
    print(f"  URL  : {result['url']}")
    print(f"  Title: {result['title']}")
    print(f"{'=' * 70}")

    print(f"\n  INPUTS ({len(result['inputs'])}):")
    for i in result['inputs']:
        print(f"    id={i['id']!r:28s} type={i['type']!r:10s} "
              f"placeholder={i['placeholder']!r:35s} "
              f"formControl={i['formControl']!r:30s} visible={i['visible']}")

    print(f"\n  BUTTONS ({len(result['buttons'])}) — visible only:")
    for b in result['buttons']:
        if b['visible']:
            print(f"    id={b['id']!r:28s} text={b['text']!r:60s}")

    print(f"\n  SELECTS ({len(result['selects'])}):")
    for s in result['selects']:
        print(f"    tag={s['tag']!r:20s} id={s['id']!r:20s} formControl={s['formControl']!r}")

    return result


async def main():
    async with async_playwright() as p:
        print("Launching Chromium (visible window)...")
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        # ── Step 1: Login page ─────────────────────────────────────────
        print(f"\nNavigating to: {PORTAL_URL}")
        await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=30000)
        await page.screenshot(path="portal_01_login.png")
        login_info = await capture(page, "LOGIN PAGE")

        # ── Step 2: Wait for user to log in and go to Form 141 ─────────
        print("\n\n>>> The browser is open and showing the login page.")
        print(">>> Please LOG IN manually with your credentials,")
        print(">>> then navigate to: e-File > File Income Tax Forms > Form 141")
        print(">>> Once you are ON the Form 141 page, come back here and press Enter.")
        input("\n>>> Press Enter when you are on Form 141: ")

        await page.screenshot(path="portal_02_form141.png")
        form141_info = await capture(page, "FORM 141 PAGE")

        # ── Step 3: Capture any sub-steps ──────────────────────────────
        more = input("\n>>> Are there more pages to capture? (y/n): ").strip().lower()
        steps = []
        step_num = 3
        while more == 'y':
            input(f">>> Navigate to the next step, then press Enter: ")
            await page.screenshot(path=f"portal_0{step_num}_step.png")
            info = await capture(page, f"STEP {step_num}")
            steps.append(info)
            step_num += 1
            more = input(">>> More pages? (y/n): ").strip().lower()

        # ── Save all captured data ─────────────────────────────────────
        output = {
            "login_page": login_info,
            "form141_page": form141_info,
            "extra_steps": steps
        }
        with open("portal_discovery.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print("\n\nAll selectors saved to: portal_discovery.json")
        print("Screenshots saved as: portal_01_login.png, portal_02_form141.png, etc.")
        await browser.close()
        print("Done.")


asyncio.run(main())
