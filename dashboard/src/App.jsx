import { useEffect, useMemo, useRef, useState } from 'react';
import mqtt from 'mqtt';

const WS_URL = import.meta.env.VITE_MQTT_WS_URL || 'ws://localhost:9001';

function safeParse(value) {
  try {
    const parsed = JSON.parse(value);
    return typeof parsed === 'object' && parsed ? parsed : { raw: value };
  } catch {
    return { raw: value };
  }
}

export default function App() {
  const clientRef = useRef(null);
  const [connection, setConnection] = useState('Disconnected');
  const [resource, setResource] = useState(null);
  const [thoughts, setThoughts] = useState([]);
  const [events, setEvents] = useState([]);

  useEffect(() => {
    const client = mqtt.connect(WS_URL);
    clientRef.current = client;

    client.on('connect', () => {
      setConnection('Connected');
      client.subscribe('system/resource/status');
      client.subscribe('cognition/thought/trace');
      client.subscribe('action/engineering/final');
      client.subscribe('action/speech/request');
      client.subscribe('system/error');
      client.subscribe('system/rag/ready');
      client.subscribe('cognition/rag/result');
    });

    client.on('reconnect', () => {
      setConnection('Reconnecting');
    });

    client.on('close', () => {
      setConnection('Disconnected');
    });

    client.on('message', (topic, message) => {
      const payload = safeParse(message.toString());

      if (topic === 'system/resource/status') {
        setResource(payload);
        return;
      }

      if (topic === 'cognition/thought/trace') {
        setThoughts((prev) => [payload, ...prev].slice(0, 8));
        return;
      }

      setEvents((prev) => [{ topic, payload, ts: Date.now() }, ...prev].slice(0, 20));
    });

    return () => {
      client.end(true);
    };
  }, []);

  const loadedModels = useMemo(() => {
    if (!resource?.loaded_models) return 'n/a';
    return resource.loaded_models.join(', ');
  }, [resource]);

  function publish(topic, payload) {
    if (!clientRef.current) return;
    clientRef.current.publish(topic, JSON.stringify(payload));
  }

  function emergencyStop() {
    publish('system/resource/pause', {
      source: 'dashboard',
      pause: true,
      reason: 'manual_emergency_stop',
      timestamp: Math.floor(Date.now() / 1000),
    });
    publish('system/brain/load/qwen', { source: 'dashboard' });
  }

  function requestVisionAnalysis() {
    publish('perception/vision/request_analysis', {
      request_id: `dash-${Date.now()}`,
      frame_hint: 'manual_dashboard_request',
      timestamp: Math.floor(Date.now() / 1000),
    });
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>MAXIMUN V5.1</h1>
        <span className={`status-pill ${connection.toLowerCase()}`}>{connection}</span>
      </header>

      <section className="panel-grid">
        <article className="panel">
          <h2>Estado cognitivo</h2>
          <div className="stats">
            <div>Modelos cargados: {loadedModels}</div>
            <div>RAM host libre: {resource?.host_available_ram_mb ?? 'n/a'} MB</div>
            <div>RAM modelos: {resource?.loaded_ram_mb ?? 'n/a'} MB</div>
            <div>CPU: {resource?.cpu_percent ?? 'n/a'}%</div>
            <div>Temperatura: {resource?.thermal_celsius ?? 'n/a'} C</div>
          </div>
          <div className="actions">
            <button className="danger" onClick={emergencyStop}>Emergency Stop</button>
            <button onClick={requestVisionAnalysis}>Analyze Vision</button>
          </div>
        </article>

        <article className="panel">
          <h2>Thought monitor (audit summary)</h2>
          <div className="feed">
            {thoughts.length === 0 && <p>No audit traces yet.</p>}
            {thoughts.map((item, idx) => (
              <div key={`${item.timestamp}-${idx}`} className="card">
                <p>{item.audit_summary || 'No summary'}</p>
                {Array.isArray(item.mandatory_changes) && item.mandatory_changes.length > 0 && (
                  <p>Mandatory changes: {item.mandatory_changes.length}</p>
                )}
              </div>
            ))}
          </div>
        </article>

        <article className="panel full-width">
          <h2>Bus events</h2>
          <div className="feed">
            {events.length === 0 && <p>No events yet.</p>}
            {events.map((item) => (
              <div key={`${item.topic}-${item.ts}`} className="card mono">
                <strong>{item.topic}</strong>
                <pre>{JSON.stringify(item.payload, null, 2)}</pre>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
