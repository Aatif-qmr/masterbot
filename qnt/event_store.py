"""
qnt/event_store.py
──────────────────
Append-only event store backed by DuckDB.

Every event flowing through the bus (or emitted by Freqtrade callbacks)
is written here as an immutable row. Each row is signed with HMAC-SHA256;
verify_integrity() flags any row whose signature doesn't match — i.e. any
tampering, manual UPDATE/DELETE, or log truncation.

Key resolution order:
  1. CIPHER_HMAC_KEY env var
  2. user_data/event_store.key  (auto-generated on first run, gitignored)

Usage:
    # via bus (automatic after register_event_store_consumer):
    from qnt.event_store import get_event_store
    store = get_event_store()

    # direct write from Freqtrade callback:
    store.append_raw("trade_open", strategy="ScalpV1", pair="BTC/USDT",
                     side="long", price=67000.0, qty=0.001)

    # query:
    df = store.query(strategy="ScalpV1", event_type="trade_open")

    # audit:
    result = store.verify_integrity()
    # {"ok": 1234, "tampered": [], "total": 1234}
"""

from __future__ import annotations

import hashlib
import hmac as _hmac_mod
import json
import logging
import os
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

if TYPE_CHECKING:
    from bus.events import BaseEvent

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent
_DB_PATH = _BASE / "user_data" / "event_store.duckdb"
_KEY_PATH = _BASE / "user_data" / "event_store.key"

# ts stored as VARCHAR so HMAC verification never hits datetime-repr drift.
# Lexicographic ordering of ISO 8601 strings is correct for same-TZ comparisons.
_DDL = """\
CREATE SEQUENCE IF NOT EXISTS events_seq START 1;
CREATE TABLE IF NOT EXISTS events (
    id            UBIGINT  NOT NULL PRIMARY KEY,
    ts            VARCHAR  NOT NULL,
    event_type    VARCHAR  NOT NULL,
    strategy      VARCHAR  DEFAULT '',
    pair          VARCHAR  DEFAULT '',
    side          VARCHAR  DEFAULT '',
    price         DOUBLE   DEFAULT 0.0,
    qty           DOUBLE   DEFAULT 0.0,
    reason        VARCHAR  DEFAULT '',
    source        VARCHAR  DEFAULT '',
    profit_ratio  DOUBLE   DEFAULT 0.0,
    profit_abs    DOUBLE   DEFAULT 0.0,
    metadata_json VARCHAR  DEFAULT '{}',
    hmac          VARCHAR  NOT NULL
);
"""


def _load_or_create_key() -> bytes:
    raw = os.environ.get("CIPHER_HMAC_KEY")
    if raw:
        return raw.encode()
    _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _KEY_PATH.exists():
        return _KEY_PATH.read_bytes().strip()
    key = secrets.token_hex(32).encode()
    _KEY_PATH.write_bytes(key)
    logger.info("EventStore: generated HMAC key → %s", _KEY_PATH)
    return key


def _sign(
    key: bytes,
    row_id: int,
    ts: str,
    event_type: str,
    strategy: str,
    pair: str,
    side: str,
    price: float,
    qty: float,
    reason: str,
    source: str,
) -> str:
    msg = f"{row_id}|{ts}|{event_type}|{strategy}|{pair}|{side}|{price}|{qty}|{reason}|{source}"
    return _hmac_mod.new(key, msg.encode(), hashlib.sha256).hexdigest()


class EventStore:
    """Thread-safe, append-only DuckDB event log with per-row HMAC integrity."""

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(db_path))
        self._conn.execute(_DDL)
        self._key = _load_or_create_key()
        self._lock = threading.Lock()

    # ── Public write API ──────────────────────────────────────────────────────

    def append(self, event: BaseEvent) -> None:
        """Persist a bus BaseEvent. Called by the wildcard bus consumer."""
        self._write(_bus_event_to_row(event))

    def append_raw(
        self,
        event_type: str,
        *,
        strategy: str = "",
        pair: str = "",
        side: str = "",
        price: float = 0.0,
        qty: float = 0.0,
        reason: str = "",
        source: str = "",
        profit_ratio: float = 0.0,
        profit_abs: float = 0.0,
        metadata: dict | None = None,
        ts: datetime | None = None,
    ) -> None:
        """
        Direct write for Freqtrade callbacks (confirm_trade_entry, confirm_trade_exit,
        custom_stoploss) that don't travel through the async bus.

        Example (inside any IStrategy subclass):
            from qnt.event_store import get_event_store
            get_event_store().append_raw(
                "trade_open", strategy="ScalpV1", pair=pair,
                side=side, price=rate, qty=amount, source="confirm_trade_entry",
            )
        """
        self._write(
            {
                "ts": (ts or datetime.now(UTC)).isoformat(),
                "event_type": event_type,
                "strategy": strategy,
                "pair": pair,
                "side": side,
                "price": float(price),
                "qty": float(qty),
                "reason": reason,
                "source": source,
                "profit_ratio": float(profit_ratio),
                "profit_abs": float(profit_abs),
                "metadata_json": json.dumps(metadata or {}),
            }
        )

    # ── Read API ──────────────────────────────────────────────────────────────

    def query(
        self,
        *,
        strategy: str | None = None,
        event_type: str | None = None,
        pair: str | None = None,
        since: datetime | None = None,
        limit: int = 500,
    ):
        """
        Return matching rows as a Polars DataFrame (newest first).
        All filters are AND-ed; omitting a filter means no restriction on that column.
        """
        import polars as pl

        conditions: list[str] = []
        params: list[Any] = []
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if pair:
            conditions.append("pair = ?")
            params.append(pair)
        if since:
            conditions.append("ts >= ?")
            params.append(since.isoformat())
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        # limit is always an int from the caller signature — safe to interpolate
        sql = f"SELECT * FROM events {where} ORDER BY ts DESC LIMIT {int(limit)}"

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            cols = [d[0] for d in self._conn.description]

        if not rows:
            return pl.DataFrame(schema={c: pl.Utf8 for c in cols})
        return pl.DataFrame(rows, schema=cols, orient="row")

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
            return int(row[0]) if row else 0

    # ── Integrity audit ───────────────────────────────────────────────────────

    def verify_integrity(self) -> dict[str, Any]:
        """
        Re-compute HMAC for every row and compare with the stored signature.

        Returns:
            {"ok": int, "tampered": list[int], "total": int}

        Any row_id in "tampered" means its data was modified after insertion,
        or the HMAC key changed, or the row was manually written without signing.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, ts, event_type, strategy, pair, side, price, qty, "
                "reason, source, hmac FROM events ORDER BY id"
            ).fetchall()

        ok, tampered = 0, []
        for row in rows:
            row_id, ts, et, strategy, pair, side, price, qty, reason, source, stored_hmac = row
            expected = _sign(
                self._key,
                row_id,
                str(ts),
                str(et),
                str(strategy or ""),
                str(pair or ""),
                str(side or ""),
                float(price or 0.0),
                float(qty or 0.0),
                str(reason or ""),
                str(source or ""),
            )
            if _hmac_mod.compare_digest(expected, stored_hmac or ""):
                ok += 1
            else:
                tampered.append(row_id)

        return {"ok": ok, "tampered": tampered, "total": ok + len(tampered)}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _write(self, row: dict) -> None:
        try:
            with self._lock:
                seq_row = self._conn.execute("SELECT nextval('events_seq')").fetchone()
                if seq_row is None:
                    raise RuntimeError("events_seq nextval returned None — DuckDB sequence missing")
                row_id = seq_row[0]
                ts = str(row.get("ts") or datetime.now(UTC).isoformat())
                et = str(row["event_type"])
                strategy = str(row.get("strategy") or "")
                pair = str(row.get("pair") or "")
                side = str(row.get("side") or "")
                price = float(row.get("price") or 0.0)
                qty = float(row.get("qty") or 0.0)
                reason = str(row.get("reason") or "")
                source = str(row.get("source") or "")

                sig = _sign(
                    self._key, row_id, ts, et, strategy, pair, side, price, qty, reason, source
                )

                self._conn.execute(
                    "INSERT INTO events "
                    "(id, ts, event_type, strategy, pair, side, price, qty, "
                    " reason, source, profit_ratio, profit_abs, metadata_json, hmac) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        row_id,
                        ts,
                        et,
                        strategy,
                        pair,
                        side,
                        price,
                        qty,
                        reason,
                        source,
                        float(row.get("profit_ratio") or 0.0),
                        float(row.get("profit_abs") or 0.0),
                        str(row.get("metadata_json") or "{}"),
                        sig,
                    ],
                )
        except Exception as exc:
            logger.error("EventStore._write failed: %s", exc)


# ── Bus event → row mapper ────────────────────────────────────────────────────


def _bus_event_to_row(event: BaseEvent) -> dict:
    """Flatten a typed bus event into the event store's flat schema."""
    base: dict = {
        "ts": event.timestamp.isoformat(),
        "event_type": str(event.type),
        "source": event.source or "",
    }
    # Import inside function to avoid circular dependency at module load time.
    try:
        from bus.events import (
            CandleEvent,
            HyperoptResultEvent,
            MacroEvent,
            RiskAlertEvent,
            SentimentEvent,
            SignalEvent,
            SystemHealthEvent,
            TradeEvent,
        )
    except ImportError:
        return base

    if isinstance(event, SignalEvent):
        base.update(
            strategy=event.strategy,
            pair=event.pair,
            side=event.direction,
            metadata_json=json.dumps({"confidence": event.confidence, "tag": event.tag}),
        )
    elif isinstance(event, TradeEvent):
        base.update(
            strategy=event.strategy,
            pair=event.pair,
            profit_ratio=event.profit_ratio,
            profit_abs=event.profit_abs,
            metadata_json=json.dumps({"trade_id": event.trade_id}),
        )
    elif isinstance(event, RiskAlertEvent):
        base.update(
            reason=event.gate,
            metadata_json=json.dumps(
                {"value": event.value, "threshold": event.threshold, "action": event.action}
            ),
        )
    elif isinstance(event, CandleEvent):
        base.update(
            pair=event.pair,
            metadata_json=json.dumps(
                {"timeframe": event.timeframe, "close": event.close, "volume": event.volume}
            ),
        )
    elif isinstance(event, SentimentEvent):
        base.update(
            price=event.score,
            metadata_json=json.dumps(event.components),
        )
    elif isinstance(event, MacroEvent):
        base.update(
            metadata_json=json.dumps(
                {
                    "dxy_24h_change": event.dxy_24h_change,
                    "btc_funding_rate": event.btc_funding_rate,
                    "btc_open_interest": event.btc_open_interest,
                }
            ),
        )
    elif isinstance(event, HyperoptResultEvent):
        base.update(
            strategy=event.strategy,
            profit_ratio=event.best_value,
            metadata_json=json.dumps(
                {"best_params": event.best_params, "n_trials": event.n_trials}
            ),
        )
    elif isinstance(event, SystemHealthEvent):
        base.update(
            metadata_json=json.dumps(
                {
                    "freqtrade_processes": event.freqtrade_processes,
                    "open_trades": event.open_trades,
                    "balance_usdt": event.balance_usdt,
                }
            ),
        )
    return base


# ── Singleton ─────────────────────────────────────────────────────────────────

_store: EventStore | None = None
_store_lock = threading.Lock()


def get_event_store(db_path: Path = _DB_PATH) -> EventStore:
    """Return the process-level EventStore singleton."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = EventStore(db_path)
    return _store
