"""Screen recording with Playwright: the animated cards and the real app, driven scene by scene."""

import math
import time
from pathlib import Path

from playwright.sync_api import Browser, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

DEMO_DIR = Path(__file__).resolve().parent
SIZE = {"width": 1920, "height": 1080}


def _context(browser: Browser, video_dir: Path, overlay: bool):
    ctx = browser.new_context(
        viewport=SIZE, device_scale_factor=1, record_video_dir=str(video_dir), record_video_size=SIZE,
        color_scheme="light", reduced_motion="no-preference",
    )
    if overlay:
        ctx.add_init_script(path=str(DEMO_DIR / "overlay.js"))
    return ctx


def record_card(browser: Browser, mode: str, seconds: float, video_dir: Path) -> dict:
    ctx = _context(browser, video_dir / mode, overlay=False)
    page = ctx.new_page()
    t_page = time.monotonic()
    page.goto((DEMO_DIR / "cards" / "card.html").as_uri() + f"?mode={mode}")
    # start the animations only once the page has painted, so a busy machine can't eat their opening
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    page.wait_for_timeout(300)
    page.evaluate("() => window.go()")
    trim = time.monotonic() - t_page
    page.wait_for_timeout(seconds * 1000 + 400)
    video = page.video.path()
    ctx.close()
    return {"video": Path(video), "trim": trim, "seconds": seconds}


class Driver:
    """Runs storyboard actions on the app page with a visible, smoothly gliding cursor."""

    def __init__(self, page: Page):
        self.page = page
        self.x, self.y = 960.0, 600.0
        page.mouse.move(self.x, self.y)

    def glide(self, x: float, y: float, ms: int = 750) -> None:
        steps = max(8, ms // 16)
        x0, y0 = self.x, self.y
        for i in range(1, steps + 1):
            t = i / steps
            e = 0.5 - 0.5 * math.cos(math.pi * t)  # ease in-out
            self.page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
            self.page.wait_for_timeout(ms / steps)
        self.x, self.y = x, y

    def centre(self, selector: str) -> tuple[float, float]:
        box = self.page.locator(selector).first.bounding_box()
        if not box:
            raise RuntimeError(f"demo: {selector!r} is not on screen")
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def do(self, action: dict) -> None:
        (kind, arg), = action.items()
        page = self.page
        if kind == "pause":
            page.wait_for_timeout(int(arg))
        elif kind == "move":
            self.glide(*self.centre(arg))
        elif kind == "click":
            self.glide(*self.centre(arg), ms=600)
            page.mouse.click(self.x, self.y)
        elif kind == "type":
            box = page.locator("#question").bounding_box()
            self.glide(box["x"] + 60, box["y"] + box["height"] / 2, ms=600)
            page.mouse.click(self.x, self.y)
            page.fill("#question", "")
            page.keyboard.type(str(arg), delay=38)
        elif kind == "submit":
            self.glide(*self.centre("form.ask-row button[type=submit]"), ms=500)
            page.mouse.click(self.x, self.y)
            try:  # the previous run's summary disappears once the new run starts
                page.wait_for_selector(".run-summary", state="detached", timeout=3000)
            except PlaywrightTimeout:
                pass
        elif kind == "wait_for":
            page.wait_for_selector(arg, state="visible", timeout=90_000)
        elif kind == "scroll_to":
            page.evaluate("s => document.querySelector(s)?.scrollIntoView({behavior: 'smooth', block: 'center'})", arg)
            page.wait_for_timeout(900)
        elif kind == "scroll_top":
            page.evaluate("() => window.scrollTo({top: 0, behavior: 'smooth'})")
            page.wait_for_timeout(900)
        elif kind == "hover_badges":
            boxes = [b.bounding_box() for b in page.locator(".graph-badge").all()[: int(arg)]]
            for box in filter(None, boxes):
                self.glide(box["x"] + box["width"] / 2 + 14, box["y"] + box["height"] / 2 + 14, ms=650)
                page.wait_for_timeout(550)
        elif kind == "spotlight":
            page.evaluate("s => window.demo.spotlight(s)", arg)
        elif kind == "hide_mascot":
            page.evaluate("() => window.demo.mascot(false)")
        elif kind == "show_mascot":
            page.evaluate("() => window.demo.mascot(true)")
        else:
            raise ValueError(f"demo: unknown action {kind!r}")


def record_app(browser: Browser, url: str, scenes: list[dict], voice: dict, video_dir: Path) -> dict:
    ctx = _context(browser, video_dir / "app", overlay=True)
    page = ctx.new_page()
    t_page = time.monotonic()
    page.goto(url)
    page.wait_for_selector(".graph canvas", timeout=60_000)
    page.wait_for_timeout(3500)  # cose layout settles
    page.evaluate("() => window.demo.showCursor()")
    driver = Driver(page)
    page.wait_for_timeout(300)
    t0 = time.monotonic()
    offsets = {}
    for scene in scenes:
        start = time.monotonic()
        offsets[scene["id"]] = start - t0
        seconds = voice[scene["id"]]["seconds"]
        page.evaluate("([c, ms]) => window.demo.say(c, ms)", [scene["caption"], int(seconds * 1000)])
        for action in scene.get("actions", []):
            driver.do(action)
        left = seconds + 0.8 - (time.monotonic() - start)
        if left > 0:
            page.wait_for_timeout(left * 1000)
    page.evaluate("() => { window.demo.spotlight(null); window.demo.wave(); }")
    page.wait_for_timeout(900)
    total = time.monotonic() - t0
    video = page.video.path()
    ctx.close()
    return {"video": Path(video), "trim": t0 - t_page, "seconds": total, "offsets": offsets}
