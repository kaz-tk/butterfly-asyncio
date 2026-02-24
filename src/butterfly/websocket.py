"""WebSocket handler for Butterfly.

Single WebSocket connection per client:
  - Binary frames (client→server): raw terminal input
  - Text frames (client→server): JSON {"type": "resize", "cols": N, "rows": N}
  - Binary frames (server→client): raw terminal output
  - Text frames (server→client): JSON {"type": "exit"} etc.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from butterfly.config import settings
from butterfly.motd import render_motd
from butterfly.session import SessionManager

logger = logging.getLogger("butterfly.ws")

ws_router = APIRouter()


@ws_router.websocket("/ws")
@ws_router.websocket("/ws/{session_id}")
async def websocket_terminal(websocket: WebSocket, session_id: str | None = None) -> None:
    """Handle a terminal WebSocket connection."""
    await websocket.accept()

    manager: SessionManager = websocket.app.state.session_manager

    # Get initial size and optional command from query params
    cols = int(websocket.query_params.get("cols", 0))
    rows = int(websocket.query_params.get("rows", 0))
    cmd = websocket.query_params.get("cmd", "")

    # Client address for motd
    remote_addr = ""
    if websocket.client:
        remote_addr = f"{websocket.client.host}:{websocket.client.port}"

    # Find or create session
    session = None
    is_new = False
    if session_id:
        session = manager.get_session(session_id)

    if session is None:
        session = await manager.create_session(cols, rows, cmd=cmd)
        is_new = True

    # Tell client which session they're connected to
    await websocket.send_text(json.dumps({"type": "session", "id": session.id}))

    # Send MOTD banner for new sessions
    if is_new:
        motd = render_motd(settings.host, settings.port, remote_addr)
        await websocket.send_bytes(motd)

    # Add client and send history
    await session.add_client(websocket)

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"]:
                # Binary frame: raw terminal input
                session.write(message["bytes"])

            elif "text" in message and message["text"]:
                # Text frame: JSON control message
                try:
                    msg = json.loads(message["text"])
                    msg_type = msg.get("type")

                    if msg_type == "resize":
                        c = int(msg.get("cols", 80))
                        r = int(msg.get("rows", 24))
                        session.resize(c, r)

                    elif msg_type == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))

                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.warning("Invalid control message: %s", e)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        session.remove_client(websocket)

        # Clean up empty sessions with dead PTY
        if not session.clients and not session.alive:
            await manager.remove_session(session.id)

        # Close WebSocket if still open
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass
