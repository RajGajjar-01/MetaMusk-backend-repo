from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


class MemoryStore:
    def __init__(self, db_url: Optional[str] = None) -> None:
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self._in_memory: Dict[str, Dict[str, Any]] = {}
        self._engine = None
        self._table = None
        self._enabled = False

        if self.db_url:
            try:
                from sqlalchemy import Column, DateTime, Float, MetaData, String, Table, Text, create_engine

                self._engine = create_engine(self.db_url)
                md = MetaData()
                self._table = Table(
                    "hallushield_claim_verifications",
                    md,
                    Column("claim_text", Text, primary_key=True),
                    Column("action", String(32), nullable=False),
                    Column("corrected_claim", Text, nullable=True),
                    Column("evidence_urls", Text, nullable=False),
                    Column("confidence", Float, nullable=False),
                    Column("created_at", DateTime, nullable=False),
                    Column("updated_at", DateTime, nullable=False),
                )
                md.create_all(self._engine)
                self._enabled = True
            except Exception:
                self._enabled = False

    def check_claim(self, claim_text: str) -> Optional[Dict[str, Any]]:
        if self._enabled and self._engine is not None and self._table is not None:
            try:
                from sqlalchemy import select

                with self._engine.begin() as conn:
                    row = (
                        conn.execute(select(self._table).where(self._table.c.claim_text == claim_text))
                        .mappings()
                        .first()
                    )
                if row:
                    return {
                        "action": row["action"],
                        "corrected_claim": row["corrected_claim"],
                        "evidence_urls": json.loads(row["evidence_urls"] or "[]"),
                        "confidence": float(row["confidence"]),
                    }
            except Exception:
                pass

        return self._in_memory.get(claim_text)

    def store_verification(
        self,
        claim_text: str,
        action: str,
        corrected_claim: Optional[str],
        evidence_urls: list[str],
        confidence: float,
    ) -> None:
        payload = {
            "action": action,
            "corrected_claim": corrected_claim,
            "evidence_urls": evidence_urls,
            "confidence": float(confidence),
        }

        self._in_memory[claim_text] = payload

        if self._enabled and self._engine is not None and self._table is not None:
            try:
                now = datetime.utcnow()
                values = {
                    "claim_text": claim_text,
                    "action": action,
                    "corrected_claim": corrected_claim,
                    "evidence_urls": json.dumps(evidence_urls),
                    "confidence": float(confidence),
                    "created_at": now,
                    "updated_at": now,
                }

                with self._engine.begin() as conn:
                    try:
                        from sqlalchemy.dialects.postgresql import insert as pg_insert

                        stmt = pg_insert(self._table).values(**values)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=[self._table.c.claim_text],
                            set_={
                                "action": stmt.excluded.action,
                                "corrected_claim": stmt.excluded.corrected_claim,
                                "evidence_urls": stmt.excluded.evidence_urls,
                                "confidence": stmt.excluded.confidence,
                                "updated_at": stmt.excluded.updated_at,
                            },
                        )
                        conn.execute(stmt)
                    except Exception:
                        try:
                            conn.execute(self._table.insert().values(**values))
                        except Exception:
                            conn.execute(
                                self._table.update()
                                .where(self._table.c.claim_text == claim_text)
                                .values(
                                    action=action,
                                    corrected_claim=corrected_claim,
                                    evidence_urls=json.dumps(evidence_urls),
                                    confidence=float(confidence),
                                    updated_at=now,
                                )
                            )
            except Exception:
                return
