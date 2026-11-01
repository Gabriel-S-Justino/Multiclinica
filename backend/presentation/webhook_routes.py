from collections.abc import Callable, Generator
from datetime import datetime
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.application.webhooks import challenge, ingest
from backend.config import Settings


def register_webhooks(
    app: FastAPI, settings: Settings, db_session: Callable[[], Generator[Session, None, None]]
) -> None:
    @app.get("/v1/webhooks/whatsapp/{channel_id}", response_class=PlainTextResponse)
    def verify(
        channel_id: UUID, request: Request, db: Session = Depends(db_session, scope="function")
    ) -> str:
        query = request.query_params
        return challenge(
            db,
            settings,
            channel_id,
            query.get("hub.mode", ""),
            query.get("hub.verify_token", ""),
            query.get("hub.challenge", ""),
        )

    async def raw_body(request: Request) -> bytes:
        return await request.body()

    @app.post("/v1/webhooks/whatsapp/{channel_id}")
    def receive(
        channel_id: UUID,
        request: Request,
        raw: bytes = Depends(raw_body),
        db: Session = Depends(db_session, scope="function"),
    ) -> dict[str, str]:
        moment = db.scalar(select(func.clock_timestamp()))
        if not isinstance(moment, datetime):
            raise RuntimeError("clock_unavailable")
        ingest(
            db, settings, channel_id, raw, request.headers.get("x-hub-signature-256", ""), moment
        )
        return {"status": "accepted"}
