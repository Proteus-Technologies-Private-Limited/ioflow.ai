#!/usr/bin/env python3
"""
Create the dedicated MQTT time-series database (ioflow_mqtt) on the
TimescaleDB docker container (localhost:5433) with the mqtt_messages
hypertable used by the "TimescaleDB MQTT Store" seed application
(backend/seed-applications/timescaledb.json).

Idempotent — safe to re-run. Requires the ioflow-postgres container
(docker compose up -d postgres).

Usage:
    venv/bin/python migrations/create_mqtt_timescale_db.py
"""

import json
import sys

HOST, PORT, USER, PASSWORD = 'localhost', 5433, 'ioflow', 'ioflow_local_pass'


def main():
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed in this environment")
        sys.exit(1)

    try:
        conn = psycopg2.connect(host=HOST, port=PORT, user=USER,
                                password=PASSWORD, dbname='ioflow', connect_timeout=10)
    except Exception as e:
        print(f"ERROR: cannot reach TimescaleDB container on {HOST}:{PORT} — {e}")
        print("Start it with: docker compose up -d postgres")
        sys.exit(1)

    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname='ioflow_mqtt'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE ioflow_mqtt OWNER ioflow")
        print("created database ioflow_mqtt")
    else:
        print("database ioflow_mqtt already exists")
    conn.close()

    conn = psycopg2.connect(host=HOST, port=PORT, user=USER,
                            password=PASSWORD, dbname='ioflow_mqtt', connect_timeout=10)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mqtt_messages (
            time        TIMESTAMPTZ NOT NULL DEFAULT now(),
            tenant_id   TEXT,
            flow_id     TEXT,
            app_id      TEXT,
            topic       TEXT NOT NULL,
            payload     JSONB,
            payload_raw TEXT,
            qos         SMALLINT DEFAULT 0,
            retain      BOOLEAN DEFAULT FALSE
        )""")
    cur.execute("SELECT create_hypertable('mqtt_messages','time', if_not_exists => TRUE)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_mqtt_messages_topic_time "
                "ON mqtt_messages (topic, time DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_mqtt_messages_tenant_time "
                "ON mqtt_messages (tenant_id, time DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_mqtt_messages_payload "
                "ON mqtt_messages USING GIN (payload)")
    try:
        cur.execute("""ALTER TABLE mqtt_messages SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'topic',
            timescaledb.compress_orderby = 'time DESC')""")
        cur.execute("SELECT add_compression_policy('mqtt_messages', INTERVAL '7 days', "
                    "if_not_exists => TRUE)")
        print("compression policy: 7 days")
    except Exception as e:
        print("compression setup skipped:", str(e).splitlines()[0])

    cur.execute("SELECT extversion FROM pg_extension WHERE extname='timescaledb'")
    print("timescaledb version:", cur.fetchone()[0])
    cur.execute("SELECT hypertable_name FROM timescaledb_information.hypertables")
    print("hypertables:", [r[0] for r in cur.fetchall()])

    # Smoke test: insert + query + delete round trip
    cur.execute("INSERT INTO mqtt_messages (topic, payload, qos, tenant_id) "
                "VALUES (%s, %s, %s, %s)",
                ('test/smoke', json.dumps({'hello': 'timescale'}), 1, 'smoke-test'))
    cur.execute("SELECT topic, payload FROM mqtt_messages WHERE tenant_id='smoke-test'")
    print("smoke row:", cur.fetchone())
    cur.execute("DELETE FROM mqtt_messages WHERE tenant_id='smoke-test'")
    conn.close()
    print("OK — ioflow_mqtt ready")


if __name__ == '__main__':
    main()
