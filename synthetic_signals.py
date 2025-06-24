import csv
import datetime as dt
import json
import os
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

import pandas as pd
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, Response
from feedgen.feed import FeedGenerator
from faker import Faker
from pydantic import BaseModel

faker = Faker()

# ─────────────── Configuration ────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_AIS_TOPIC = os.getenv("KAFKA_AIS_TOPIC", "ais_positions")
AIS_MSGS_PER_SEC = int(os.getenv("AIS_MSGS_PER_SEC", "12000"))

PORT_CONGESTION_INTERVAL_SEC = int(os.getenv("PORT_REFRESH_SEC", "900"))  # 15 min
WEATHER_FEED_INTERVAL_SEC = int(os.getenv("WEATHER_REFRESH_SEC", "900"))
NEWS_FEED_INTERVAL_SEC = int(os.getenv("NEWS_REFRESH_SEC", "1800"))

SUPPLIER_TABLE_PATH = Path(
    os.getenv("SUPPLIER_TABLE_PATH", "supplier_vessel_mapping.csv")
)
SUPPLIER_TABLE_ROWS = int(os.getenv("SUPPLIER_TABLE_ROWS", "100000"))
SUPPLIER_TABLE_REFRESH_HOURS = int(os.getenv("SUPPLIER_TABLE_REFRESH_HOURS", "24"))

PORTS = [
    "Shanghai",
    "Singapore",
    "Ningbo‑Zhoushan",
    "Shenzhen",
    "Guangzhou",
    "Busan",
    "Qingdao",
    "Hamburg",
    "Los Angeles",
    "Long Beach",
]
SEVERITY_LEVELS = ["Minor", "Moderate", "Severe", "Extreme"]
GEOPOLITICAL_THEMES = [
    "Sanctions",
    "Trade Agreement",
    "Regulatory Change",
    "Labor Strike",
    "Tariff Increase",
    "Embargo",
    "Border Closure",
]


# ─────────────── Data Models ────────────────
class AISMessage(BaseModel):
    mmsi: int  # Maritime Mobile Service Identity
    imo: int  # International Maritime Organization number
    lat: float
    lon: float
    sog: float  # speed over ground (knots)
    cog: float  # course over ground (degrees)
    timestamp: str  # ISO 8601


class PortCongestionRecord(BaseModel):
    port: str
    queued_vessels: int
    avg_wait_hours: float
    updated_at: str


# ───────────────️ AIS Producer ────────────────
async def ais_producer(stop_event: asyncio.Event) -> None:
    """Continuously push synthetic AIS JSON messages to Kafka."""
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        metadata_max_age_ms=30000,  # Refresh metadata every 30 seconds
        request_timeout_ms=30000,  # 30 second timeout for requests
        retry_backoff_ms=100,  # Backoff between retries
    )

    # Add retry logic for producer startup
    max_retries = 5
    for attempt in range(max_retries):
        try:
            await producer.start()
            print(f"[AIS] Producer started → topic {KAFKA_AIS_TOPIC}")
            break
        except Exception as e:
            print(
                f"[AIS] Producer start attempt {attempt + 1}/{max_retries} failed: {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2**attempt)  # Exponential backoff
            else:
                raise
    try:
        msgs_per_tick = AIS_MSGS_PER_SEC // 10  # send 10×/sec to smooth load
        tick_interval = 0.1
        while not stop_event.is_set():
            now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
            batch: List[bytes] = []
            for _ in range(msgs_per_tick):
                msg = AISMessage(
                    mmsi=random.randint(200000000, 799999999),
                    imo=random.randint(9000000, 9999999),
                    lat=faker.coordinate(center=0, radius=90),
                    lon=faker.coordinate(center=0, radius=180),
                    sog=round(random.uniform(0, 22), 1),
                    cog=round(random.uniform(0, 359), 0),
                    timestamp=now_iso,
                )
                batch.append(msg.model_dump_json().encode())
            # Send messages with error handling
            for b in batch:
                try:
                    await producer.send_and_wait(KAFKA_AIS_TOPIC, b)
                except Exception as e:
                    print(f"[AIS] Failed to send message: {e}")
                    # Continue with next message rather than crashing
            await asyncio.sleep(tick_interval)
    finally:
        await producer.stop()
        print("[AIS] Producer stopped")


# ─────────────── Supplier↔Vessel CSV ────────────────
async def refresh_supplier_table(stop_event: asyncio.Event) -> None:
    """Regenerates CSV on a cadence to simulate nightly loads."""
    while not stop_event.is_set():
        print("[SUPPLIERS] Generating table →", SUPPLIER_TABLE_PATH)
        with SUPPLIER_TABLE_PATH.open("w", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(["supplier_id", "supplier_name", "imo", "last_updated"])
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            for sid in range(1, SUPPLIER_TABLE_ROWS + 1):
                writer.writerow(
                    [
                        sid,
                        faker.company(),
                        random.randint(9000000, 9999999),
                        now,
                    ]
                )
        await asyncio.sleep(SUPPLIER_TABLE_REFRESH_HOURS * 3600)


# ─────────────── Port Congestion Snapshot ────────────────
_port_cache: List[PortCongestionRecord] = []


def _generate_port_congestion() -> None:
    """Populate the in‑memory port congestion cache."""
    global _port_cache
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    _port_cache = [
        PortCongestionRecord(
            port=p,
            queued_vessels=random.randint(0, 80),
            avg_wait_hours=round(random.uniform(0, 72), 1),
            updated_at=now_iso,
        )
        for p in PORTS
    ]


async def port_congestion_refresher(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        _generate_port_congestion()
        await asyncio.sleep(PORT_CONGESTION_INTERVAL_SEC)


# ─────────────── RSS Feed Helpers ────────────────
_weather_feed_xml: str = ""
_news_feed_xml: str = ""


def _mk_feed(title: str) -> FeedGenerator:
    fg = FeedGenerator()
    # python-feedgen already outputs RSS; no extension module required
    fg.title(title)
    fg.link(href="http://localhost:8000")
    fg.description("Synthetic data feed")
    fg.language("en")
    return fg


def _refresh_weather_feed():
    global _weather_feed_xml
    fg = _mk_feed("Synthetic Severe Weather Feed")
    for _ in range(random.randint(1, 5)):
        fe = fg.add_entry()
        fe.id(faker.uuid4())
        fe.title(f"{random.choice(SEVERITY_LEVELS)} storm near {faker.city()}")
        fe.summary(faker.sentence())
        fe.published(dt.datetime.now(dt.timezone.utc))
    _weather_feed_xml = fg.rss_str(pretty=True).decode()


def _refresh_news_feed():
    global _news_feed_xml
    fg = _mk_feed("Synthetic Geopolitical News")
    for _ in range(random.randint(1, 3)):
        fe = fg.add_entry()
        fe.id(faker.uuid4())
        theme = random.choice(GEOPOLITICAL_THEMES)
        fe.title(f"{theme} impacts shipping through {faker.country()}")
        fe.summary(faker.paragraph())
        fe.published(dt.datetime.now(dt.timezone.utc))
    _news_feed_xml = fg.rss_str(pretty=True).decode()


async def rss_refresher(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        _refresh_weather_feed()
        _refresh_news_feed()
        await asyncio.sleep(min(WEATHER_FEED_INTERVAL_SEC, NEWS_FEED_INTERVAL_SEC))


# ─────────────── FastAPI App ────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    stop_event = asyncio.Event()
    app.state.stop_event = stop_event

    # Initialize data
    _generate_port_congestion()
    try:
        _refresh_weather_feed()
        _refresh_news_feed()
    except Exception as e:
        print(f"[STARTUP] Error initializing RSS feeds: {e}")

    # Start background tasks
    tasks = [
        asyncio.create_task(ais_producer(stop_event)),
        asyncio.create_task(port_congestion_refresher(stop_event)),
        asyncio.create_task(rss_refresher(stop_event)),
        asyncio.create_task(refresh_supplier_table(stop_event)),
    ]

    yield

    # Shutdown
    stop_event.set()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(
    title="Synthetic Magentic Signal Endpoints", version="0.1.0", lifespan=lifespan
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/port_congestion", response_model=List[PortCongestionRecord])
async def port_congestion():
    return _port_cache


@app.get("/rss/weather")
async def weather_rss():
    return Response(content=_weather_feed_xml, media_type="application/rss+xml")


@app.get("/rss/geopolitics")
async def geopolitics_rss():
    return Response(content=_news_feed_xml, media_type="application/rss+xml")


@app.get("/supplier_mapping")
async def supplier_mapping(n: int = 100):
    """Return the first *n* supplier‑vessel rows as JSON for quick inspection."""
    df = pd.read_csv(SUPPLIER_TABLE_PATH, nrows=n)
    return json.loads(df.to_json(orient="records"))


# ─────────────── CLI Entrypoint ────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "synthetic_signals:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
