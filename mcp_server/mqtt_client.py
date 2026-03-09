"""Persistent MQTT client with QoS 1. Publishes structured events for all OpenSCAD operations."""

import json
import logging
import os
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)

_client: mqtt.Client | None = None
_lock = threading.Lock()


def _get_client() -> mqtt.Client | None:
    """Get or create a persistent MQTT connection. Returns None if broker unavailable."""
    global _client
    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client

        broker = os.environ.get("MQTT_BROKER", "localhost")
        port = int(os.environ.get("MQTT_PORT", "1883"))

        try:
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id="openscad-mcp",
                protocol=mqtt.MQTTv311,
            )
            client.connect(broker, port, keepalive=60)
            client.loop_start()
            _client = client
            log.info("MQTT connected: %s:%d", broker, port)
            return _client
        except Exception as e:
            log.warning("MQTT unavailable (%s:%d): %s — publishing disabled", broker, port, e)
            return None


def publish(topic: str, payload: dict) -> bool:
    """Publish a JSON payload to an MQTT topic with QoS 1. Returns True on success."""
    client = _get_client()
    if client is None:
        return False

    payload["timestamp"] = datetime.now(timezone.utc).isoformat()

    try:
        info = client.publish(topic, json.dumps(payload), qos=1)
        info.wait_for_publish(timeout=5)
        log.debug("MQTT published: %s", topic)
        return True
    except Exception as e:
        log.warning("MQTT publish failed (%s): %s", topic, e)
        return False


def publish_event(category: str, event: str, data: dict) -> bool:
    """Publish to openscad/{category}/{event}."""
    return publish(f"openscad/{category}/{event}", data)


def disconnect():
    """Clean shutdown."""
    global _client
    if _client is not None:
        _client.loop_stop()
        _client.disconnect()
        _client = None
        log.info("MQTT disconnected")
