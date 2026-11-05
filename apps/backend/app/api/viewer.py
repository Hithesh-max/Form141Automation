import os
import asyncio
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from apps.backend.app.database.config import get_db
from apps.backend.app.database import models
from apps.backend.app.services.browser_viewer_service import browser_viewer_service
from apps.backend.app.services.session_service import session_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["Browser Viewer"])


def _resolve_vnc_host() -> str:
    """
    Resolve the private VNC server hostname.

    In Docker, the VNC server runs in the worker container.
    Outside Docker, it normally runs on localhost.
    """
    env_host = os.getenv("VNC_HOST")

    if env_host:
        return env_host

    if os.path.exists("/.dockerenv") or os.getenv("ENV") == "production":
        return "worker"

    return "127.0.0.1"


VNC_HOST = _resolve_vnc_host()
VNC_PORT = int(os.getenv("VNC_PORT", "5900"))


@router.get("/{job_id}/viewer", response_class=HTMLResponse)
def get_browser_viewer_page(
    job_id: int,
    token: str = Query(
        ...,
        description="Cryptographically signed viewer session token",
    ),
    db: Session = Depends(get_db),
):
    """
    Serve the authenticated remote browser viewer page.
    """

    # Verify the signed viewer token.
    token_payload = browser_viewer_service.verify_token(
        token,
        expected_job_id=job_id,
    )

    if not token_payload:
        return HTMLResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content="""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Access Denied - Form 141 Browser Session</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }

        .card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 32px;
            max-width: 480px;
            text-align: center;
        }

        h2 {
            color: #f43f5e;
        }

        p {
            color: #94a3b8;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="card">
        <h2>Session Access Denied or Expired</h2>
        <p>
            The browser viewer link is invalid, has expired,
            or does not belong to this filing job.
        </p>
        <p>
            Return to the dashboard and click
            <strong>Open Browser Session</strong>
            to obtain a fresh link.
        </p>
    </div>
</body>
</html>""",
        )

    # Load the job.
    job = db.query(models.Job).filter(models.Job.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    # Load customer information.
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.id == job.customer_id)
        .first()
    )

    customer_name = customer.name if customer else "Unknown Client"
    job_ref = job.job_reference or f"JOB-{job.id}"

    # Check whether the browser session is available.
    session_meta = session_service.get_session_metadata(job.id)
    session_available = bool(
        session_meta
        and session_meta.get("session_available", False)
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Form 141 - Remote Browser Session [{job_ref}]</title>

    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                Roboto,
                sans-serif;

            background: #0b0f19;
            color: #f3f4f6;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        .header {{
            background: #111827;
            border-bottom: 1px solid #1f2937;
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 10px;
            z-index: 10;
        }}

        .header-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .header-right {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 12px;
            color: #9ca3af;
        }}

        .badge-ref {{
            background: #1f2937;
            border: 1px solid #374151;
            color: #e5e7eb;
            padding: 3px 8px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 12px;
            font-weight: 600;
        }}

        .status-badge {{
            background: #d97706;
            color: #ffffff;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 4px 10px;
            border-radius: 9999px;
            letter-spacing: 0.05em;
        }}

        .client-name {{
            font-size: 14px;
            font-weight: 600;
            color: #f9fafb;
        }}

        .warning-banner {{
            background: #78350f;
            border-bottom: 1px solid #92400e;
            color: #fef3c7;
            font-size: 12px;
            padding: 8px 20px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .viewer-container {{
            flex: 1;
            background: #030712;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}

        .status-overlay {{
            position: absolute;
            background: rgba(17, 24, 39, 0.95);
            border: 1px solid #374151;
            border-radius: 8px;
            padding: 24px;
            text-align: center;
            max-width: 440px;
            color: #9ca3af;
            font-size: 13px;
            line-height: 1.6;
            z-index: 20;
        }}

        .status-overlay h3 {{
            color: #f3f4f6;
            margin-bottom: 8px;
        }}

        .btn-refresh {{
            background: #2563eb;
            color: #ffffff;
            border: none;
            padding: 7px 14px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 12px;
        }}

        .btn-refresh:hover {{
            background: #1d4ed8;
        }}

        .btn-close {{
            background: #374151;
            margin-top: 0;
        }}

        .btn-close:hover {{
            background: #4b5563;
        }}
    </style>
</head>

<body>
    <div class="header">
        <div class="header-left">
            <span class="badge-ref">{job_ref}</span>
            <span class="client-name">{customer_name}</span>
            <span class="status-badge">{job.status}</span>
        </div>

        <div class="header-right">
            <span>🔒 Authenticated Session</span>
            <button
                onclick="window.close()"
                class="btn-refresh btn-close"
            >
                Close Viewer
            </button>
        </div>
    </div>

    <div class="warning-banner">
        ⚠️
        <strong>CONFIDENTIAL TAX DATA:</strong>
        This remote browser session is strictly for manual review
        and payment authorization of Form 141. All actions are logged.
    </div>

    <div class="viewer-container" id="screen">
        <div
            id="status_overlay"
            class="status-overlay"
            style="display: none;"
        >
            <h3 id="overlay_title">
                Connecting to Remote Session...
            </h3>

            <p id="overlay_msg">
                Establishing secure WebSocket stream
                to the remote Chromium display.
            </p>

            <button
                class="btn-refresh"
                onclick="location.reload()"
            >
                Reconnect
            </button>
        </div>
    </div>

    <script type="module">
        /*
         * Import the complete module namespace first.
         *
         * Depending on how rfb.bundle.js was generated, RFB may be:
         * - the default export
         * - a named RFB export
         * - nested inside default.RFB
         * - nested inside default.default
         */
        import * as RFBModule from '/api/static/novnc/rfb.bundle.js';

        const RFB =
            typeof RFBModule.default === "function"
                ? RFBModule.default
                : typeof RFBModule.RFB === "function"
                    ? RFBModule.RFB
                    : typeof RFBModule.default?.RFB === "function"
                        ? RFBModule.default.RFB
                        : typeof RFBModule.default?.default === "function"
                            ? RFBModule.default.default
                            : null;

        console.log("[Viewer] Loaded noVNC module:", RFBModule);
        console.log("[Viewer] Resolved RFB type:", typeof RFB);

        const jobId = {job_id};
        const token = "{token}";

        const screenElem = document.getElementById("screen");
        const overlay = document.getElementById("status_overlay");
        const overlayTitle = document.getElementById("overlay_title");
        const overlayMsg = document.getElementById("overlay_msg");

        function showStatus(title, message) {{
            overlayTitle.textContent = title;
            overlayMsg.textContent = message;
            overlay.style.display = "block";
        }}

        function hideStatus() {{
            overlay.style.display = "none";
        }}

        if (typeof RFB !== "function") {{
            console.error(
                "[Viewer] Unable to resolve noVNC RFB constructor.",
                RFBModule
            );

            showStatus(
                "Viewer Initialization Error",
                "The noVNC RFB client was loaded, but its constructor could not be resolved."
            );
        }} else {{
            showStatus(
                "Connecting to Remote Display",
                "Establishing secure WebSocket connection to remote Chromium session..."
            );

            const wsProtocol =
                window.location.protocol === "https:"
                    ? "wss:"
                    : "ws:";

            const wsUrl =
                `${{wsProtocol}}//${{window.location.host}}` +
                `/api/jobs/${{jobId}}/vnc-stream?token=${{encodeURIComponent(token)}}`;

            console.log("[Viewer] Connecting to:", wsUrl);

            let rfb = null;

            try {{
                rfb = new RFB(screenElem, wsUrl, {{
                    credentials: {{
                        password: ""
                    }}
                }});

                rfb.scaleViewport = true;
                rfb.clipViewport = false;
                rfb.resizeSession = false;

                rfb.addEventListener("connect", () => {{
                    console.log(
                        "[Viewer] RFB connection established to remote display."
                    );

                    hideStatus();

                    if (typeof rfb.focus === "function") {{
                        rfb.focus();
                    }}
                }});

                rfb.addEventListener("disconnect", (event) => {{
                    console.log(
                        "[Viewer] RFB disconnected:",
                        event.detail
                    );

                    const clean = event.detail?.clean;

                    showStatus(
                        "Session Disconnected",
                        clean
                            ? "The remote browser session has ended."
                            : "The display stream disconnected. The filing may have completed or the session may have closed."
                    );
                }});

                rfb.addEventListener("securityfailure", (event) => {{
                    console.error(
                        "[Viewer] VNC security failure:",
                        event.detail
                    );

                    showStatus(
                        "Authentication Error",
                        "The VNC security handshake failed. Please obtain a fresh session token."
                    );
                }});

            }} catch (error) {{
                console.error(
                    "[Viewer] RFB initialization error:",
                    error
                );

                showStatus(
                    "Viewer Initialization Error",
                    error.message ||
                        "Failed to initialize the remote RFB client."
                );
            }}
        }}
    </script>
</body>
</html>"""

    return HTMLResponse(content=html_content)


@router.websocket("/{job_id}/vnc-stream")
async def vnc_stream_proxy(
    websocket: WebSocket,
    job_id: int,
    token: str = Query(
        ...,
        description="Viewer session token",
    ),
):
    """
    Authenticated WebSocket proxy.

    Browser viewer
        -> FastAPI WebSocket endpoint
        -> private worker:5900 VNC server

    Port 5900 is never exposed publicly.
    """

    # Verify the viewer token.
    payload = browser_viewer_service.verify_token(
        token,
        expected_job_id=job_id,
    )

    if not payload:
        await websocket.close(
            code=1008,
            reason="Unauthorized or expired viewer token",
        )
        return

    await websocket.accept()

    reader = None
    writer = None

    # Connect to the private VNC server.
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                VNC_HOST,
                VNC_PORT,
            ),
            timeout=5.0,
        )

        logger.info(
            "Connected to VNC server at %s:%s for job %s",
            VNC_HOST,
            VNC_PORT,
            job_id,
        )

    except Exception as error:
        logger.warning(
            "VNC server unavailable at %s:%s for job %s: %s",
            VNC_HOST,
            VNC_PORT,
            job_id,
            error,
        )

        await websocket.close(
            code=1011,
            reason="Remote VNC server offline or unconfigured",
        )
        return

    async def client_to_vnc():
        """
        Forward binary data from the browser viewer to VNC.
        """
        try:
            while True:
                data = await websocket.receive_bytes()

                if not data:
                    break

                writer.write(data)
                await writer.drain()

        except (
            WebSocketDisconnect,
            asyncio.CancelledError,
        ):
            pass

        except Exception as error:
            logger.debug(
                "Client-to-VNC stream ended: %s",
                error,
            )

        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def vnc_to_client():
        """
        Forward binary data from VNC to the browser viewer.
        """
        try:
            while True:
                data = await reader.read(8192)

                if not data:
                    break

                await websocket.send_bytes(data)

        except (
            WebSocketDisconnect,
            asyncio.CancelledError,
        ):
            pass

        except Exception as error:
            logger.debug(
                "VNC-to-client stream ended: %s",
                error,
            )

        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    try:
        await asyncio.gather(
            client_to_vnc(),
            vnc_to_client(),
            return_exceptions=True,
        )

    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

        logger.info(
            "VNC WebSocket proxy closed for job %s",
            job_id,
        )