from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine, select

metadata = MetaData()

bans_table = Table(
    "bans",
    metadata,
    Column("token_hash", String(128), primary_key=True),
    Column("reason", String(128), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

strikes_table = Table(
    "strikes",
    metadata,
    Column("token_hash", String(128), primary_key=True),
    Column("count", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

self_harm_table = Table(
    "self_harm",
    metadata,
    Column("token_hash", String(128), primary_key=True),
    Column("count", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

incidents_table = Table(
    "incidents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("type", String(64), nullable=False),
    Column("token_hash", String(128), nullable=False),
    Column("role", String(32), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("metadata", String(512), nullable=True),
)


def init_engine(db_url: str, retries: int = 10, delay_seconds: int = 2):
    engine = create_engine(db_url, future=True, pool_pre_ping=True)
    last_exc: Exception | None = None
    attempts = max(1, retries)
    for attempt in range(attempts):
        try:
            with engine.connect():
                last_exc = None
                break
        except Exception as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(max(1, delay_seconds))
    if last_exc:
        raise last_exc
    metadata.create_all(engine)
    return engine


@dataclass
class Persistence:
    engine: any

    def is_banned(self, token_hash: str) -> bool:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            result = conn.execute(
                select(bans_table.c.token_hash).where(
                    bans_table.c.token_hash == token_hash, bans_table.c.expires_at > now
                )
            ).first()
            return result is not None

    def ban_token(self, token_hash: str, reason: str | None, retention_days: int) -> None:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=retention_days)
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(bans_table.c.token_hash).where(bans_table.c.token_hash == token_hash)
            ).first()
            if existing:
                conn.execute(
                    bans_table.update()
                    .where(bans_table.c.token_hash == token_hash)
                    .values(reason=reason, expires_at=expires_at)
                )
            else:
                conn.execute(
                    bans_table.insert().values(
                        token_hash=token_hash, reason=reason, created_at=now, expires_at=expires_at
                    )
                )

    def increment_strike(self, token_hash: str, amount: int) -> int:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            row = conn.execute(
                select(strikes_table.c.count).where(strikes_table.c.token_hash == token_hash)
            ).first()
            if row:
                count = int(row[0]) + amount
                conn.execute(
                    strikes_table.update()
                    .where(strikes_table.c.token_hash == token_hash)
                    .values(count=count, updated_at=now)
                )
                return count
            conn.execute(
                strikes_table.insert().values(token_hash=token_hash, count=amount, updated_at=now)
            )
            return amount

    def increment_self_harm(self, token_hash: str, amount: int) -> int:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self_harm_table.c.count).where(self_harm_table.c.token_hash == token_hash)
            ).first()
            if row:
                count = int(row[0]) + amount
                conn.execute(
                    self_harm_table.update()
                    .where(self_harm_table.c.token_hash == token_hash)
                    .values(count=count, updated_at=now)
                )
                return count
            conn.execute(
                self_harm_table.insert().values(token_hash=token_hash, count=amount, updated_at=now)
            )
            return amount

    def log_incident(self, incident_type: str, token_hash: str, role: str | None, metadata_value: str | None) -> None:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            conn.execute(
                incidents_table.insert().values(
                    id=str(uuid4()),
                    type=incident_type,
                    token_hash=token_hash,
                    role=role,
                    created_at=now,
                    metadata=metadata_value,
                )
            )

    def cleanup_expired(self, incident_retention_days: int) -> None:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=incident_retention_days)
        with self.engine.begin() as conn:
            conn.execute(bans_table.delete().where(bans_table.c.expires_at <= now))
            conn.execute(incidents_table.delete().where(incidents_table.c.created_at <= cutoff))

    def list_bans(self) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(select(bans_table)).fetchall()
        return [
            {"token_hash": row.token_hash, "expires_at": row.expires_at}
            for row in rows
            if row.expires_at is None or row.expires_at > datetime.now(timezone.utc)
        ]

    def lift_ban(self, token_hash: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(bans_table.delete().where(bans_table.c.token_hash == token_hash))

    def list_incidents(self, limit: int = 100) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(incidents_table).order_by(incidents_table.c.created_at.desc()).limit(limit)
            ).fetchall()
        return [
            {
                "type": row.type,
                "token_hash": row.token_hash,
                "role": row.role,
                "timestamp": row.created_at,
                "metadata": row.metadata,
            }
            for row in rows
        ]
