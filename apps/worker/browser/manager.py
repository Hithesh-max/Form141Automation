import os
import uuid
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def _get_worker_chrome_pids(worker_pid: int) -> set[int]:
    """Finds all child/descendant Chromium process IDs belonging to this worker on Windows."""
    if os.name != 'nt':
        return set()
    try:
        import ctypes
        from ctypes import wintypes
        
        TH32CS_SNAPPROCESS = 0x00000002
        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ('dwSize', wintypes.DWORD),
                ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD),
                ('th32DefaultHeapID', ctypes.c_void_p),
                ('th32ModuleID', wintypes.DWORD),
                ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD),
                ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', wintypes.DWORD),
                ('szExeFile', ctypes.c_char * 260)
            ]
            
        kernel32 = ctypes.windll.kernel32
        hSnapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not hSnapshot or hSnapshot == -1:
            return set()
            
        pe32 = PROCESSENTRY32()
        pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
        procs = []
        if kernel32.Process32First(hSnapshot, ctypes.byref(pe32)):
            while True:
                exe_name = pe32.szExeFile.decode('ansi', 'ignore').lower()
                procs.append((pe32.th32ProcessID, pe32.th32ParentProcessID, exe_name))
                if not kernel32.Process32Next(hSnapshot, ctypes.byref(pe32)):
                    break
        kernel32.CloseHandle(hSnapshot)

        descendants = {worker_pid}
        added = True
        while added:
            added = False
            for p_id, p_parent, name in procs:
                if p_parent in descendants and p_id not in descendants:
                    descendants.add(p_id)
                    added = True
        return {p_id for p_id, p_parent, name in procs if p_id in descendants and 'chrome' in name}
    except Exception as e:
        logger.debug(f"Process PID discovery note: {e}")
        return set()

def _activate_windows_foreground(match_hint: Optional[str] = None, target_pid: Optional[int] = None) -> bool:
    """
    Brings the exact Chromium window associated with the job to the OS foreground on Windows.
    Matches window strictly by Chromium process ID and window title.
    """
    if os.name != 'nt':
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        target_pids = set()
        if target_pid:
            target_pids.add(target_pid)
        # Discover all child Chromium PIDs of this worker process
        child_pids = _get_worker_chrome_pids(os.getpid())
        target_pids.update(child_pids)
        
        matched_hwnd = None
        candidate_hwnds = []

        def enum_cb(hwnd, lparam):
            nonlocal matched_hwnd
            if user32.IsWindowVisible(hwnd):
                class_name = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_name, 256)
                if class_name.value == 'Chrome_WidgetWin_1':
                    window_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                    if not target_pids or window_pid.value in target_pids:
                        length = user32.GetWindowTextLengthW(hwnd)
                        title_buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, title_buf, length + 1)
                        title_str = title_buf.value
                        candidate_hwnds.append((hwnd, window_pid.value, title_str))
                        if match_hint and match_hint.lower() in title_str.lower():
                            matched_hwnd = hwnd
                            return False # Found exact title match
            return True
            
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        # If exact title match not found, pick the top candidate from worker's Chromium PIDs
        if not matched_hwnd and candidate_hwnds:
            matched_hwnd = candidate_hwnds[0][0]

        if matched_hwnd:
            current_thread_id = kernel32.GetCurrentThreadId()
            window_thread_id = user32.GetWindowThreadProcessId(matched_hwnd, None)
            user32.AttachThreadInput(current_thread_id, window_thread_id, True)
            user32.ShowWindow(matched_hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(matched_hwnd)
            user32.AttachThreadInput(current_thread_id, window_thread_id, False)
            logger.info(f"Activated Windows HWND {matched_hwnd} for Chromium session")
            return True
        return False
    except Exception as e:
        logger.debug(f"Windows OS window activation note: {e}")
        return False

class BrowserManager:
    def __init__(self, headless=False):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        # JobSession registry: job_id -> JobSession runtime dict
        self.sessions: Dict[int, Dict[str, Any]] = {}
        self._redis_client = None

    @property
    def redis(self):
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                self._redis_client.ping()
            except Exception:
                self._redis_client = None
        return self._redis_client

    async def start(self):
        logger.info("Starting real Chromium browser instance...")
        # Clear any stale session keys from prior crashed/restarted workers
        r = self.redis
        if r:
            try:
                keys = r.keys("form141:sessions:*")
                if keys:
                    r.delete(*keys)
            except Exception as e:
                logger.debug(f"Redis session cleanup note: {e}")

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--window-size=1280,800",
                "--window-position=0,0",
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-extensions",
                "--disable-features=Translate",
                "--lang=en-IN",
            ]
        )
        logger.info("Real Chromium browser started successfully.")

    async def create_context(self) -> BrowserContext:
        context = await self.browser.new_context(
            no_viewport=True,
            # User agent must match the actual Playwright Chromium build version to avoid fingerprint mismatch
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        # Mask navigator.webdriver and other automation fingerprints at page load time
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-GB', 'en'] });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        """)
        return context

    async def register_session(
        self,
        job_id: int,
        job_reference: str,
        customer_id: int,
        filing_id: Optional[int],
        context: BrowserContext,
        page: Page,
        state: str = "PAYMENT_PENDING"
    ) -> Dict[str, Any]:
        """
        Registers an isolated runtime browser session for a specific job.
        Never serializes Playwright objects outside the process.
        """
        jid = int(job_id)
        browser_context_id = f"ctx-{uuid.uuid4().hex[:8]}"
        page_id = f"page-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Discover PID of Chromium
        chrome_pids = _get_worker_chrome_pids(os.getpid())
        pid = min(chrome_pids) if chrome_pids else os.getpid()

        url = page.url if page and not page.is_closed() else ""
        try:
            title = await page.title() if page and not page.is_closed() else ""
        except Exception:
            title = ""

        session_entry = {
            "job_id": jid,
            "job_reference": job_reference,
            "customer_id": customer_id,
            "filing_id": filing_id,
            "context": context,
            "page": page,
            "browser_context_id": browser_context_id,
            "page_id": page_id,
            "pid": pid,
            "url": url,
            "title": title,
            "created_at": now_iso,
            "last_activity_at": now_iso,
            "state": state,
            "session_available": True
        }

        # Handle page or context closed by employee directly in Chromium UI
        def _on_closed():
            logger.info(f"[{job_reference}] Browser page/tab closed by user. Updating session registry.")
            session_entry["session_available"] = False
            session_entry["state"] = "CLOSED"
            self._sync_redis_metadata(jid, session_entry)

        page.on("close", lambda p: _on_closed())
        context.on("close", lambda c: _on_closed())

        self.sessions[jid] = session_entry
        self._sync_redis_metadata(jid, session_entry)

        reg_log = (
            f"\n[SESSION_REGISTERED]\n"
            f"job_id={job_reference}\n"
            f"context={browser_context_id}\n"
            f"page={page_id}\n"
            f"url={url}\n"
            f"title={title}\n"
            f"pid={pid}\n"
            f"session_available=true\n"
        )
        print(reg_log)
        logger.info(reg_log)

        return {
            "job_id": jid,
            "job_reference": job_reference,
            "browser_context_id": browser_context_id,
            "page_id": page_id,
            "pid": pid,
            "url": url,
            "title": title,
            "session_available": True
        }

    def _sync_redis_metadata(self, job_id: int, session: Dict[str, Any]):
        """Persists safe runtime presence metadata to Redis (no Playwright objects or secrets)."""
        r = self.redis
        if not r:
            return
        try:
            safe_meta = {
                "job_id": session["job_id"],
                "job_reference": session["job_reference"],
                "customer_id": session["customer_id"],
                "filing_id": session.get("filing_id"),
                "browser_context_id": session["browser_context_id"],
                "page_id": session["page_id"],
                "pid": session.get("pid"),
                "url": session.get("url"),
                "title": session.get("title"),
                "session_available": session["session_available"],
                "state": session["state"],
                "created_at": session["created_at"],
                "last_activity_at": session.get("last_activity_at")
            }
            key = f"form141:sessions:{job_id}"
            if session["session_available"]:
                r.set(key, json.dumps(safe_meta), ex=86400)
            else:
                r.delete(key)
        except Exception as e:
            logger.debug(f"Redis session sync note: {e}")

    def has_session(self, job_id: Any) -> bool:
        """Check synchronously if job is registered in local active sessions."""
        try:
            return int(job_id) in self.sessions
        except (ValueError, TypeError):
            return False

    async def open_session(self, job_id: int) -> Dict[str, Any]:
        """
        Locates the exact job's browser context and brings its tab & OS window to front.
        Idempotent: repeatedly focusing an open session will not spawn new browsers or tabs.
        """
        try:
            jid = int(job_id)
        except (ValueError, TypeError):
            jid = job_id

        session = self.sessions.get(jid)
        if not session or not session.get("session_available"):
            logger.warning(f"[JOB-{jid}] Open session failed: session unavailable in registry.")
            return {
                "success": False,
                "session_available": False,
                "reason": "SESSION_UNAVAILABLE",
                "detail": "Browser session unavailable (worker restarted or window closed)."
            }

        page: Page = session.get("page")
        if not page or page.is_closed():
            session["session_available"] = False
            session["state"] = "CLOSED"
            self._sync_redis_metadata(jid, session)
            logger.warning(f"[JOB-{jid}] Open session failed: page is closed.")
            return {
                "success": False,
                "session_available": False,
                "reason": "SESSION_UNAVAILABLE",
                "detail": "Browser session unavailable (window closed)."
            }

        try:
            # 1. Bring tab to front in Chromium context
            await page.bring_to_front()
            
            # 2. Bring Chromium window to front at OS level on Windows
            job_ref = session.get("job_reference") or str(jid)
            _activate_windows_foreground(match_hint=job_ref, target_pid=session.get("pid"))

            session["last_activity_at"] = datetime.now(timezone.utc).isoformat()
            self._sync_redis_metadata(jid, session)

            url = page.url
            try:
                title = await page.title()
            except Exception:
                title = session.get("title", "")

            focus_log = (
                f"\n[SESSION_FOCUSED]\n"
                f"job_id={session['job_reference']}\n"
                f"context={session['browser_context_id']}\n"
                f"page={session['page_id']}\n"
                f"url={url}\n"
                f"title={title}\n"
                f"pid={session.get('pid')}\n"
                f"session_available=true\n"
            )
            print(focus_log)
            logger.info(focus_log)

            return {
                "success": True,
                "session_available": True,
                "job_id": jid,
                "job_reference": session["job_reference"],
                "browser_context_id": session["browser_context_id"],
                "page_id": session["page_id"],
                "url": url,
                "title": title
            }
        except Exception as e:
            logger.error(f"Error bringing session to front for job {jid}: {e}")
            return {
                "success": False,
                "session_available": False,
                "reason": str(e)
            }

    async def close_session(self, job_id: int) -> Dict[str, Any]:
        """
        Safely closes the browser context and cleans up the session registry for a specific job.
        Does not affect any other job's session.
        """
        try:
            jid = int(job_id)
        except (ValueError, TypeError):
            jid = job_id

        session = self.sessions.pop(jid, None)
        if not session:
            r = self.redis
            if r:
                try:
                    r.delete(f"form141:sessions:{jid}")
                except Exception:
                    pass
            return {"success": True, "session_available": False, "job_id": jid}

        session["session_available"] = False
        session["state"] = "CLOSED"
        self._sync_redis_metadata(jid, session)

        context: BrowserContext = session.get("context")
        if context:
            try:
                await context.close()
                logger.info(f"[{session.get('job_reference')}] Cleaned up browser context.")
            except Exception as e:
                logger.debug(f"Context close note: {e}")

        return {"success": True, "session_available": False, "job_id": jid}

    def check_session(self, job_id: int) -> Dict[str, Any]:
        """Checks if an active, unclosed session exists for the given job_id."""
        try:
            jid = int(job_id)
        except (ValueError, TypeError):
            jid = job_id

        session = self.sessions.get(jid)
        if not session:
            return {"success": True, "session_available": False, "job_id": jid}
        page: Page = session.get("page")
        is_avail = bool(session.get("session_available") and page and not page.is_closed())
        return {
            "success": True,
            "session_available": is_avail,
            "job_id": jid,
            "job_reference": session.get("job_reference"),
            "browser_context_id": session.get("browser_context_id")
        }

    async def stop(self):
        logger.info("Closing all remaining active browser sessions...")
        for job_id in list(self.sessions.keys()):
            await self.close_session(job_id)
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser stopped.")
