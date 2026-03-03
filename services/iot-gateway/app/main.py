from __future__ import annotations

import asyncio
import json
import os
import signal
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import paho.mqtt.client as mqtt

try:
    from bleak import BleakScanner

    BLEAK_AVAILABLE = True
except ImportError:
    BleakScanner = None
    BLEAK_AVAILABLE = False

try:
    import serial
    import serial.tools.list_ports

    SERIAL_AVAILABLE = True
except ImportError:
    serial = None
    SERIAL_AVAILABLE = False

try:
    import minimalmodbus

    MODBUS_AVAILABLE = True
except ImportError:
    minimalmodbus = None
    MODBUS_AVAILABLE = False

try:
    from opcua import Client as OpcUaClient

    OPCUA_AVAILABLE = True
except ImportError:
    OpcUaClient = None
    OPCUA_AVAILABLE = False

try:
    import can

    CAN_AVAILABLE = True
except ImportError:
    can = None
    CAN_AVAILABLE = False


def _env_bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).strip().lower() == "true"


class IoTGateway:
    def __init__(self) -> None:
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_username = os.getenv("MQTT_USERNAME", "")
        self.mqtt_password = os.getenv("MQTT_PASSWORD", "")
        self.mqtt_tls_enable = os.getenv("MQTT_TLS_ENABLE", "false").lower() == "true"
        self.mqtt_tls_ca_cert = os.getenv("MQTT_TLS_CA_CERT", "")
        self.mqtt_tls_client_cert = os.getenv("MQTT_TLS_CLIENT_CERT", "")
        self.mqtt_tls_client_key = os.getenv("MQTT_TLS_CLIENT_KEY", "")
        self.mqtt_tls_insecure = os.getenv("MQTT_TLS_INSECURE", "false").lower() == "true"

        self.enable_iot = _env_bool("ENABLE_IOT", True)
        self.simulation = _env_bool("IOT_SIMULATION", True)
        self.enable_bluetooth = _env_bool("IOT_ENABLE_BLUETOOTH", True)
        self.enable_zigbee = _env_bool("IOT_ENABLE_ZIGBEE", True)
        self.enable_industrial = _env_bool("IOT_ENABLE_INDUSTRIAL", True)
        self.status_interval_sec = int(os.getenv("IOT_STATUS_INTERVAL_SEC", "25"))

        self.bluetooth_timeout_sec = float(os.getenv("IOT_BLUETOOTH_TIMEOUT_SEC", "6.0"))
        self.zigbee_serial_port = os.getenv("IOT_ZIGBEE_SERIAL_PORT", "/dev/ttyUSB1")
        self.zigbee_baudrate = int(os.getenv("IOT_ZIGBEE_BAUDRATE", "115200"))

        self.modbus_serial_port = os.getenv("IOT_MODBUS_SERIAL_PORT", "/dev/ttyUSB2")
        self.modbus_baudrate = int(os.getenv("IOT_MODBUS_BAUDRATE", "9600"))

        self.opcua_endpoint = os.getenv("IOT_OPCUA_ENDPOINT", "opc.tcp://127.0.0.1:4840")
        self.opcua_default_node = os.getenv("IOT_OPCUA_DEFAULT_NODE", "ns=2;i=2")

        self.can_channel = os.getenv("IOT_CAN_CHANNEL", "can0")
        self.can_interface = os.getenv("IOT_CAN_INTERFACE", "socketcan")

        self.stop_event = threading.Event()
        self.pause_requested = False
        self.mqtt_connected = False
        self.stats = {
            "requests_total": 0,
            "bluetooth_scans": 0,
            "zigbee_scans": 0,
            "industrial_calls": 0,
            "errors": 0,
        }
        self.stats_lock = threading.Lock()

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="iot-gateway")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self._configure_mqtt_security()

    def start(self) -> None:
        self._install_signal_handlers()

        if not self.enable_iot:
            print("[iot-gateway] ENABLE_IOT=false, servicio en espera pasiva")

        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.client.loop_start()
        threading.Thread(target=self._status_loop, daemon=True).start()

        while not self.stop_event.is_set():
            time.sleep(0.4)

        self.client.loop_stop()
        self.client.disconnect()

    def stop(self) -> None:
        self.stop_event.set()

    def _configure_mqtt_security(self) -> None:
        if self.mqtt_username:
            self.client.username_pw_set(self.mqtt_username, self.mqtt_password)

        if self.mqtt_tls_enable:
            self.client.tls_set(
                ca_certs=self.mqtt_tls_ca_cert or None,
                certfile=self.mqtt_tls_client_cert or None,
                keyfile=self.mqtt_tls_client_key or None,
            )
            self.client.tls_insecure_set(self.mqtt_tls_insecure)

    def on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        self.mqtt_connected = True
        print(f"[iot-gateway] MQTT conectado rc={reason_code}")

        client.subscribe("iot/gateway/command")
        client.subscribe("iot/bluetooth/scan/request")
        client.subscribe("iot/zigbee/scan/request")
        client.subscribe("iot/industrial/request")
        client.subscribe("system/resource/pause")

        self._publish(
            "system/iot/ready",
            {
                "service": "iot-gateway",
                "status": "online",
                "simulation": self.simulation,
                "capabilities": self._capabilities(),
                "timestamp": int(time.time()),
            },
        )

    def on_disconnect(self, client: mqtt.Client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.mqtt_connected = False
        print(f"[iot-gateway] MQTT desconectado rc={reason_code}")

    def on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        payload = self._decode_payload(msg.payload)

        if topic == "system/resource/pause":
            self.pause_requested = bool(payload.get("pause", False))
            self._publish(
                "system/iot/status",
                {
                    "service": "iot-gateway",
                    "pause_requested": self.pause_requested,
                    "timestamp": int(time.time()),
                },
            )
            return

        threading.Thread(target=self._handle_operation, args=(topic, payload), daemon=True).start()

    def _status_loop(self) -> None:
        while not self.stop_event.is_set():
            self._publish(
                "system/iot/status",
                {
                    "service": "iot-gateway",
                    "status": "running",
                    "pause_requested": self.pause_requested,
                    "simulation": self.simulation,
                    "capabilities": self._capabilities(),
                    "stats": self._stats_snapshot(),
                    "timestamp": int(time.time()),
                },
            )
            time.sleep(max(3, self.status_interval_sec))

    def _handle_operation(self, topic: str, payload: Dict[str, Any]) -> None:
        with self.stats_lock:
            self.stats["requests_total"] += 1

        request_id = str(payload.get("request_id", f"iot-{int(time.time() * 1000)}"))
        operation = "unknown"
        result: Dict[str, Any]
        output_topic = "iot/gateway/response"

        try:
            if topic == "iot/bluetooth/scan/request":
                operation = "scan_bluetooth"
                output_topic = "perception/iot/bluetooth/devices"
                result = self._scan_bluetooth(payload)
            elif topic == "iot/zigbee/scan/request":
                operation = "scan_zigbee"
                output_topic = "perception/iot/zigbee/devices"
                result = self._scan_zigbee(payload)
            elif topic == "iot/industrial/request":
                operation = "industrial_request"
                output_topic = "perception/iot/industrial/data"
                result = self._industrial_request(payload)
            elif topic == "iot/gateway/command":
                operation = str(payload.get("action", "unknown"))
                result, output_topic = self._dispatch_gateway_command(payload)
            else:
                result = self._error("topic_not_supported", f"topic no soportado: {topic}")
        except Exception as exc:
            with self.stats_lock:
                self.stats["errors"] += 1
            result = self._error("internal_error", str(exc))

        message = {
            "service": "iot-gateway",
            "request_id": request_id,
            "operation": operation,
            "result": result,
            "timestamp": int(time.time()),
        }
        self._publish(output_topic, message)

        if output_topic != "iot/gateway/response":
            self._publish("iot/gateway/response", message)

    def _dispatch_gateway_command(self, payload: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        action = str(payload.get("action", "")).strip().lower()

        if action == "scan_bluetooth":
            return self._scan_bluetooth(payload), "perception/iot/bluetooth/devices"
        if action == "scan_zigbee":
            return self._scan_zigbee(payload), "perception/iot/zigbee/devices"
        if action in {"industrial", "industrial_request"}:
            return self._industrial_request(payload), "perception/iot/industrial/data"
        if action == "get_status":
            status_payload = {
                "stats": self._stats_snapshot(),
                "capabilities": self._capabilities(),
            }
            return self._ok(status_payload), "iot/gateway/response"

        return self._error("unknown_action", f"accion no soportada: {action}"), "iot/gateway/response"

    def _scan_bluetooth(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enable_bluetooth:
            return self._error("bluetooth_disabled", "IOT_ENABLE_BLUETOOTH=false")

        with self.stats_lock:
            self.stats["bluetooth_scans"] += 1

        timeout_sec = float(payload.get("timeout_sec", self.bluetooth_timeout_sec))
        if self.simulation or not BLEAK_AVAILABLE:
            devices = [
                {"name": "MAX-SENSOR-A", "address": "AA:BB:CC:11:22:01", "rssi": -58},
                {"name": "MAX-BLE-LOCK", "address": "AA:BB:CC:11:22:02", "rssi": -71},
            ]
            return self._ok(
                {
                    "mode": "simulation" if self.simulation else "fallback",
                    "bleak_available": BLEAK_AVAILABLE,
                    "devices": devices,
                }
            )

        devices = asyncio.run(self._bleak_discover(timeout_sec))
        return self._ok({"mode": "real", "devices": devices, "count": len(devices)})

    async def _bleak_discover(self, timeout_sec: float) -> List[Dict[str, Any]]:
        discovered = await BleakScanner.discover(timeout=max(1.0, timeout_sec))
        devices: List[Dict[str, Any]] = []
        for dev in discovered:
            devices.append(
                {
                    "name": getattr(dev, "name", None),
                    "address": getattr(dev, "address", None),
                    "rssi": getattr(dev, "rssi", None),
                    "details": str(getattr(dev, "details", ""))[:120],
                }
            )
        return devices

    def _scan_zigbee(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enable_zigbee:
            return self._error("zigbee_disabled", "IOT_ENABLE_ZIGBEE=false")

        with self.stats_lock:
            self.stats["zigbee_scans"] += 1

        port = str(payload.get("port", self.zigbee_serial_port))
        baudrate = int(payload.get("baudrate", self.zigbee_baudrate))

        if self.simulation or not SERIAL_AVAILABLE:
            devices = [
                {"ieee": "0x00124b0024aa1001", "short": "0x81A2", "type": "temperature_sensor"},
                {"ieee": "0x00124b0024aa1002", "short": "0x81A3", "type": "smart_relay"},
            ]
            return self._ok(
                {
                    "mode": "simulation" if self.simulation else "fallback",
                    "serial_available": SERIAL_AVAILABLE,
                    "coordinator_port": port,
                    "baudrate": baudrate,
                    "devices": devices,
                }
            )

        if not Path(port).exists():
            return self._error("zigbee_port_missing", f"coordinador Zigbee no detectado en {port}")

        ports = []
        for item in serial.tools.list_ports.comports():
            ports.append(
                {
                    "device": item.device,
                    "description": item.description,
                    "vid": item.vid,
                    "pid": item.pid,
                    "manufacturer": item.manufacturer,
                }
            )

        return self._ok(
            {
                "mode": "real",
                "coordinator_port": port,
                "baudrate": baudrate,
                "detected_ports": ports,
                "note": "escaneo de red Zigbee requiere stack del coordinador (zigpy/zigbee2mqtt)",
            }
        )

    def _industrial_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enable_industrial:
            return self._error("industrial_disabled", "IOT_ENABLE_INDUSTRIAL=false")

        with self.stats_lock:
            self.stats["industrial_calls"] += 1

        protocol = str(payload.get("protocol", "modbus")).strip().lower()
        if protocol == "modbus":
            return self._modbus_request(payload)
        if protocol in {"opcua", "opc-ua"}:
            return self._opcua_request(payload)
        if protocol == "can":
            return self._can_request(payload)
        return self._error("protocol_not_supported", f"protocolo no soportado: {protocol}")

    def _modbus_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.simulation or not MODBUS_AVAILABLE:
            data = {
                "mode": "simulation" if self.simulation else "fallback",
                "modbus_available": MODBUS_AVAILABLE,
                "register": int(payload.get("register", 100)),
                "value": 42,
                "unit": "raw",
            }
            return self._ok(data)

        port = str(payload.get("port", self.modbus_serial_port))
        slave_id = int(payload.get("slave_id", 1))
        register = int(payload.get("register", 0))
        decimals = int(payload.get("decimals", 0))
        function_code = int(payload.get("function_code", 3))
        signed = bool(payload.get("signed", False))
        operation = str(payload.get("operation", "read")).strip().lower()

        if not Path(port).exists():
            return self._error("modbus_port_missing", f"puerto Modbus no encontrado: {port}")

        instrument = minimalmodbus.Instrument(port, slave_id)
        instrument.serial.baudrate = int(payload.get("baudrate", self.modbus_baudrate))
        instrument.serial.timeout = float(payload.get("timeout_sec", 1.0))

        if operation == "write":
            write_value = int(payload.get("value", 0))
            instrument.write_register(register, write_value, functioncode=16)
            return self._ok(
                {
                    "mode": "real",
                    "protocol": "modbus_rtu",
                    "operation": "write",
                    "register": register,
                    "value": write_value,
                }
            )

        value = instrument.read_register(
            registeraddress=register,
            number_of_decimals=decimals,
            functioncode=function_code,
            signed=signed,
        )
        return self._ok(
            {
                "mode": "real",
                "protocol": "modbus_rtu",
                "operation": "read",
                "register": register,
                "value": value,
            }
        )

    def _opcua_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.simulation or not OPCUA_AVAILABLE:
            data = {
                "mode": "simulation" if self.simulation else "fallback",
                "opcua_available": OPCUA_AVAILABLE,
                "endpoint": payload.get("endpoint", self.opcua_endpoint),
                "node_id": payload.get("node_id", self.opcua_default_node),
                "value": 21.7,
            }
            return self._ok(data)

        endpoint = str(payload.get("endpoint", self.opcua_endpoint))
        node_id = str(payload.get("node_id", self.opcua_default_node))
        operation = str(payload.get("operation", "read")).strip().lower()

        client = OpcUaClient(endpoint, timeout=float(payload.get("timeout_sec", 3.0)))
        client.connect()
        try:
            node = client.get_node(node_id)
            if operation == "write":
                value = payload.get("value")
                node.set_value(value)
                return self._ok(
                    {
                        "mode": "real",
                        "protocol": "opcua",
                        "operation": "write",
                        "endpoint": endpoint,
                        "node_id": node_id,
                        "value": value,
                    }
                )

            value = node.get_value()
            return self._ok(
                {
                    "mode": "real",
                    "protocol": "opcua",
                    "operation": "read",
                    "endpoint": endpoint,
                    "node_id": node_id,
                    "value": value,
                }
            )
        finally:
            client.disconnect()

    def _can_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.simulation or not CAN_AVAILABLE:
            frame = {"arbitration_id": 0x123, "data": [1, 2, 3, 4], "is_extended_id": False}
            return self._ok(
                {
                    "mode": "simulation" if self.simulation else "fallback",
                    "can_available": CAN_AVAILABLE,
                    "frame": frame,
                }
            )

        channel = str(payload.get("channel", self.can_channel))
        interface = str(payload.get("interface", self.can_interface))
        operation = str(payload.get("operation", "read")).strip().lower()

        bus = can.interface.Bus(channel=channel, interface=interface)
        try:
            if operation == "send":
                arbitration_id = _parse_int(payload.get("arbitration_id", "0x123"))
                data = payload.get("data", [1, 2, 3, 4])
                if not isinstance(data, list):
                    return self._error("invalid_can_data", "campo data debe ser lista de bytes")
                msg = can.Message(
                    arbitration_id=arbitration_id,
                    data=[int(v) & 0xFF for v in data[:8]],
                    is_extended_id=bool(payload.get("is_extended_id", False)),
                )
                bus.send(msg, timeout=float(payload.get("timeout_sec", 1.0)))
                return self._ok(
                    {
                        "mode": "real",
                        "protocol": "can",
                        "operation": "send",
                        "channel": channel,
                        "arbitration_id": arbitration_id,
                    }
                )

            frame = bus.recv(timeout=float(payload.get("timeout_sec", 1.5)))
            if frame is None:
                return self._ok(
                    {
                        "mode": "real",
                        "protocol": "can",
                        "operation": "read",
                        "channel": channel,
                        "frame": None,
                    }
                )
            return self._ok(
                {
                    "mode": "real",
                    "protocol": "can",
                    "operation": "read",
                    "channel": channel,
                    "frame": {
                        "arbitration_id": int(frame.arbitration_id),
                        "data": list(frame.data),
                        "is_extended_id": bool(frame.is_extended_id),
                        "dlc": int(frame.dlc),
                    },
                }
            )
        finally:
            if hasattr(bus, "shutdown"):
                bus.shutdown()

    def _capabilities(self) -> Dict[str, Any]:
        return {
            "bluetooth": self.enable_bluetooth,
            "zigbee": self.enable_zigbee,
            "industrial": self.enable_industrial,
            "libraries": {
                "bleak": BLEAK_AVAILABLE,
                "pyserial": SERIAL_AVAILABLE,
                "minimalmodbus": MODBUS_AVAILABLE,
                "opcua": OPCUA_AVAILABLE,
                "python_can": CAN_AVAILABLE,
            },
        }

    def _stats_snapshot(self) -> Dict[str, int]:
        with self.stats_lock:
            return dict(self.stats)

    def _publish(self, topic: str, payload: Dict[str, Any]) -> None:
        if not self.mqtt_connected:
            return
        self.client.publish(topic, json.dumps(payload, ensure_ascii=True), qos=0, retain=False)

    @staticmethod
    def _ok(data: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "data": data}

    @staticmethod
    def _error(code: str, message: str) -> Dict[str, Any]:
        return {"status": "error", "error_code": code, "message": message}

    @staticmethod
    def _decode_payload(payload_raw: bytes) -> Dict[str, Any]:
        if not payload_raw:
            return {}
        text = payload_raw.decode("utf-8", errors="replace").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            return {"raw": parsed}
        except json.JSONDecodeError:
            return {"text": text}

    def _install_signal_handlers(self) -> None:
        def _handler(signum, frame) -> None:
            self.stop()

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)


def _parse_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return int(str(value), 0)


if __name__ == "__main__":
    service = IoTGateway()
    service.start()
