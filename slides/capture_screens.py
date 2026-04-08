"""Capture Streamlit screenshots via headless Chromium."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "assets"
URL = "http://localhost:8765"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1100}, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(8000)

    # 1. Main view (map collapsed)
    page.screenshot(path=str(OUT / "ui_main.png"), full_page=False)
    print("wrote ui_main.png")

    # 2. Expand the resort map and screenshot it
    try:
        page.get_by_text("Show Resort Map").click()
        page.wait_for_timeout(5000)  # let plotly render
        page.screenshot(path=str(OUT / "ui_map.png"), full_page=False)
        print("wrote ui_map.png")
    except Exception as e:
        print("map expand failed:", e)

    # 3. Full-page screenshot for backup
    page.screenshot(path=str(OUT / "ui_full.png"), full_page=True)
    print("wrote ui_full.png")

    browser.close()
