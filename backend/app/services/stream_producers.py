"""In-process background producers for Kafka and MQTT outputs — the "real
background-task execution model" WebSocketStream's docstring flags as
needed for anything that doesn't have a client connection to hang its
production loop on. Deliberately the simplest honest version: a producer
is an `asyncio.Task` tracked in a module-level registry, started when its
KafkaOutput/MQTTOutput row is created and cancelled when it's deleted —
not resumed automatically if the backend process restarts (a documented
gap, the same kind of tradeoff WebSocketStream already accepts by not
persisting "running" state at all). Single-process only: running multiple
backend workers would start independent, duplicate producers for the same
output — fine for this project's single-container docker-compose
deployment, not something to rely on beyond that.

A connection failure (broker unreachable, wrong topic, etc.) doesn't raise
into the caller or hang the task forever — it retries with a fixed
backoff up to a small bounded number of times, then gives up and the task
exits quietly. Check the backend's logs to see why a producer stopped.
"""

import asyncio
import contextlib
import json
import logging
import urllib.request
from typing import Any
from uuid import UUID, uuid4

from app.db import session as db_session
from app.models.kafka_output import KafkaOutput
from app.models.mqtt_output import MQTTOutput
from app.models.rabbitmq_output import RabbitMQOutput
from app.models.webhook_output import WebhookOutput
from app.services import metrics, webhook_signing
from app.services.generator import build_lookup_pools, generate_rows

logger = logging.getLogger(__name__)

_tasks: dict[UUID, asyncio.Task] = {}

# Parallel to _tasks, kept in sync by start/stop: which broker kind each
# running task is. Only the monitoring gauges need this (see
# app.services.metrics) — the loops themselves never look at it, which is
# why it's a separate dict rather than complicating _tasks' value type.
_task_kinds: dict[UUID, str] = {}


def task_kinds() -> list[str]:
    return list(_task_kinds.values())


CONNECT_TIMEOUT_SECONDS = 5
RETRY_BACKOFF_SECONDS = 5
MAX_CONSECUTIVE_FAILURES = 5


def _load_batch_sync(
    model: type, output_id: UUID, source: str
) -> tuple[list[dict[str, Any]], float] | None:
    """One short-lived session, plain data out — same reasoning as
    websocket_streams._generate_batch_sync, including looking up
    `db_session.SessionLocal` fresh each call so tests can override it.
    Returns None if the output row is gone (deleted mid-run), the signal
    for the calling loop to stop."""
    db = db_session.SessionLocal()
    try:
        output = db.get(model, output_id)
        if output is None:
            return None
        entity = output.entity
        with metrics.generation(source) as recorder:
            rows = generate_rows(
                entity.fields,
                output.batch_size,
                fk_pools=build_lookup_pools(entity.lookup_attachments),
                rules=entity.rules,
                workflows=entity.workflows,
                trends=entity.trends,
                error_injections=entity.error_injections,
                event_triggers=entity.event_triggers,
                geo_routes=entity.geo_routes,
            )
            recorder.count(len(rows))
        return rows, output.events_per_second
    finally:
        db.close()


async def _kafka_loop(output_id: UUID, bootstrap_servers: str, topic: str) -> None:
    # Imported here, not at module scope: aiokafka is an optional extra
    # (see app.services.install), so this module has to import cleanly on
    # an MQTT-only install. The create route already refused if it's
    # missing, so by the time this runs the import is safe.
    from aiokafka import AIOKafkaProducer

    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        request_timeout_ms=CONNECT_TIMEOUT_SECONDS * 1000,
    )
    started = False
    failures = 0
    try:
        while True:
            try:
                if not started:
                    await producer.start()
                    started = True
                result = await asyncio.to_thread(_load_batch_sync, KafkaOutput, output_id, "kafka")
                if result is None:
                    return
                rows, events_per_second = result
                for row in rows:
                    await producer.send_and_wait(topic, json.dumps(row).encode())
                metrics.record_delivery("kafka")
                failures = 0
                await asyncio.sleep(1 / events_per_second)
            except asyncio.CancelledError:
                raise
            except Exception:
                failures += 1
                started = False
                metrics.record_delivery_error("kafka")
                logger.warning(
                    "Kafka producer %s failed (attempt %s/%s)",
                    output_id,
                    failures,
                    MAX_CONSECUTIVE_FAILURES,
                    exc_info=True,
                )
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error("Kafka producer %s giving up", output_id)
                    return
                await asyncio.sleep(RETRY_BACKOFF_SECONDS)
    finally:
        if started:
            with contextlib.suppress(Exception):
                await producer.stop()


async def _mqtt_loop(output_id: UUID, host: str, port: int, topic: str) -> None:
    # Optional extra — see the note in _kafka_loop.
    from aiomqtt import Client as MQTTClient

    failures = 0
    while True:
        try:
            client_ctx = MQTTClient(hostname=host, port=port, timeout=CONNECT_TIMEOUT_SECONDS)
            async with client_ctx as client:
                failures = 0
                while True:
                    result = await asyncio.to_thread(
                        _load_batch_sync, MQTTOutput, output_id, "mqtt"
                    )
                    if result is None:
                        return
                    rows, events_per_second = result
                    for row in rows:
                        await client.publish(topic, payload=json.dumps(row).encode())
                    metrics.record_delivery("mqtt")
                    await asyncio.sleep(1 / events_per_second)
        except asyncio.CancelledError:
            raise
        except Exception:
            failures += 1
            metrics.record_delivery_error("mqtt")
            logger.warning(
                "MQTT producer %s failed (attempt %s/%s)",
                output_id,
                failures,
                MAX_CONSECUTIVE_FAILURES,
                exc_info=True,
            )
            if failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error("MQTT producer %s giving up", output_id)
                return
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)


async def _webhook_loop(output_id: UUID, url: str, secret: str) -> None:
    """POST signed batches to a URL.

    The request itself goes through `urllib` on a worker thread rather than
    an async HTTP client. Adding one would mean a new core dependency for a
    single POST — the same trade `synthflow check` made — and the thread
    keeps the event loop free while the receiver takes its time.

    A batch is sent as one JSON array, not one request per row: a receiver
    being asked to handle 50 requests a second where one would do is a
    denial of service dressed as a feature.
    """
    failures = 0
    while True:
        try:
            result = await asyncio.to_thread(_load_batch_sync, WebhookOutput, output_id, "webhook")
            if result is None:
                return
            rows, events_per_second = result
            await asyncio.to_thread(_post_signed, url, secret, rows)
            metrics.record_delivery("webhook")
            failures = 0
            await asyncio.sleep(1 / events_per_second)
        except asyncio.CancelledError:
            raise
        except Exception:
            failures += 1
            metrics.record_delivery_error("webhook")
            logger.warning(
                "Webhook producer %s failed (attempt %s/%s)",
                output_id,
                failures,
                MAX_CONSECUTIVE_FAILURES,
                exc_info=True,
            )
            if failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error("Webhook producer %s giving up", output_id)
                return
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)


def _post_signed(url: str, secret: str, rows: list[dict[str, Any]]) -> None:
    """Blocking POST with an HMAC signature over the exact bytes sent."""
    body = json.dumps(rows).encode()
    signature, timestamp = webhook_signing.sign(secret, body)
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header(webhook_signing.SIGNATURE_HEADER, signature)
    request.add_header(webhook_signing.TIMESTAMP_HEADER, str(timestamp))
    request.add_header(webhook_signing.DELIVERY_HEADER, str(uuid4()))
    with urllib.request.urlopen(request, timeout=CONNECT_TIMEOUT_SECONDS) as response:
        # Any 2xx is success. Draining the body matters: leaving it unread
        # keeps the connection from being reused and slowly leaks sockets.
        response.read()


async def _rabbitmq_loop(
    output_id: UUID,
    host: str,
    port: int,
    vhost: str,
    username: str,
    password: str,
    exchange_name: str,
    routing_key: str,
) -> None:
    # Optional extra — see the note in _kafka_loop.
    import aio_pika

    failures = 0
    while True:
        try:
            connection = await asyncio.wait_for(
                aio_pika.connect_robust(
                    host=host,
                    port=port,
                    virtualhost=vhost,
                    login=username,
                    password=password,
                ),
                timeout=CONNECT_TIMEOUT_SECONDS,
            )
            async with connection:
                channel = await connection.channel()
                # An empty exchange name is RabbitMQ's default exchange,
                # where the routing key *is* the queue name — the simplest
                # thing that works for someone who just wants messages in a
                # queue. `get_exchange` rather than `declare_exchange` for a
                # named one: declaring would create it with our guess at its
                # settings, and silently creating infrastructure on someone
                # else's broker is worse than failing.
                exchange = (
                    channel.default_exchange
                    if not exchange_name
                    else await channel.get_exchange(exchange_name)
                )
                if not exchange_name:
                    await _warn_if_queue_missing(connection, routing_key, output_id)
                failures = 0
                while True:
                    result = await asyncio.to_thread(
                        _load_batch_sync, RabbitMQOutput, output_id, "rabbitmq"
                    )
                    if result is None:
                        return
                    rows, events_per_second = result
                    for row in rows:
                        await exchange.publish(
                            aio_pika.Message(body=json.dumps(row).encode()),
                            routing_key=routing_key,
                        )
                    metrics.record_delivery("rabbitmq")
                    await asyncio.sleep(1 / events_per_second)
        except asyncio.CancelledError:
            raise
        except Exception:
            failures += 1
            metrics.record_delivery_error("rabbitmq")
            logger.warning(
                "RabbitMQ producer %s failed (attempt %s/%s)",
                output_id,
                failures,
                MAX_CONSECUTIVE_FAILURES,
                exc_info=True,
            )
            if failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error("RabbitMQ producer %s giving up", output_id)
                return
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)


def start_webhook_producer(output: WebhookOutput) -> None:
    _tasks[output.id] = asyncio.create_task(_webhook_loop(output.id, output.url, output.secret))
    _task_kinds[output.id] = "webhook"


def start_rabbitmq_producer(output: RabbitMQOutput) -> None:
    _tasks[output.id] = asyncio.create_task(
        _rabbitmq_loop(
            output.id,
            output.host,
            output.port,
            output.vhost,
            output.username,
            output.password,
            output.exchange,
            output.routing_key,
        )
    )
    _task_kinds[output.id] = "rabbitmq"


async def _warn_if_queue_missing(connection, queue_name: str, output_id: UUID) -> None:
    """Say something when messages are about to vanish.

    Publishing to RabbitMQ's default exchange with a routing key that no
    queue is named after is not an error — the broker accepts the message
    and silently discards it. So a misconfigured output reports success,
    delivers nothing, and gives the user nothing to go on. That is the
    exact failure mode Phase 11 exists to surface.

    The check is a passive declare, which the broker answers by closing the
    channel if the queue is absent. It therefore runs on a throwaway
    channel so a missing queue cannot take down the one we publish on. It
    is a warning rather than a hard failure because the queue may
    legitimately be declared later by whatever consumer is being written.
    """
    probe = await connection.channel()
    try:
        await probe.get_queue(queue_name)
    except Exception:
        logger.warning(
            "RabbitMQ producer %s publishes to the default exchange with routing key "
            "'%s', but no queue of that name exists. RabbitMQ will accept and silently "
            "discard these messages until one is declared.",
            output_id,
            queue_name,
        )
    finally:
        with contextlib.suppress(Exception):
            await probe.close()


def start_kafka_producer(output: KafkaOutput) -> None:
    _tasks[output.id] = asyncio.create_task(
        _kafka_loop(output.id, output.bootstrap_servers, output.topic)
    )
    _task_kinds[output.id] = "kafka"


def start_mqtt_producer(output: MQTTOutput) -> None:
    _tasks[output.id] = asyncio.create_task(
        _mqtt_loop(output.id, output.broker_host, output.broker_port, output.topic)
    )
    _task_kinds[output.id] = "mqtt"


def stop_producer(output_id: UUID) -> None:
    _task_kinds.pop(output_id, None)
    task = _tasks.pop(output_id, None)
    if task is not None:
        task.cancel()


async def stop_all_producers() -> None:
    """Called on app shutdown so no task outlives the process."""
    tasks = list(_tasks.values())
    _tasks.clear()
    _task_kinds.clear()
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
