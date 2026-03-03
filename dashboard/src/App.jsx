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

function nowTs() {
  return Math.floor(Date.now() / 1000);
}

function shortText(input, max = 240) {
  const text = String(input || '').trim();
  if (!text) return 'n/a';
  if (text.length <= max) return text;
  return `${text.slice(0, max)}...`;
}

export default function App() {
  const clientRef = useRef(null);
  const [connection, setConnection] = useState('Disconnected');
  const [resource, setResource] = useState(null);
  const [thoughts, setThoughts] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [finals, setFinals] = useState([]);
  const [events, setEvents] = useState([]);
  const [overrideAudit, setOverrideAudit] = useState(false);
  const [approvalComment, setApprovalComment] = useState('');
  const [lastRagInteractionId, setLastRagInteractionId] = useState('');

  useEffect(() => {
    const client = mqtt.connect(WS_URL);
    clientRef.current = client;

    client.on('connect', () => {
      setConnection('Connected');
      client.subscribe('system/resource/status');
      client.subscribe('cognition/thought/trace');
      client.subscribe('project/engineering/draft');
      client.subscribe('action/engineering/final');
      client.subscribe('action/engineering/approval_ack');
      client.subscribe('system/audit/override_ack');
      client.subscribe('system/resource/failsafe');
      client.subscribe('system/integrity/violation');
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
        setThoughts((prev) => [payload, ...prev].slice(0, 10));
        return;
      }

      if (topic === 'project/engineering/draft') {
        setDrafts((prev) => [payload, ...prev].slice(0, 10));
        return;
      }

      if (topic === 'action/engineering/final') {
        setFinals((prev) => [payload, ...prev].slice(0, 20));
        return;
      }

      if (topic === 'system/audit/override_ack') {
        setOverrideAudit(Boolean(payload.enabled));
      }

      if (topic === 'cognition/rag/result' && typeof payload.interaction_id === 'string') {
        setLastRagInteractionId(payload.interaction_id);
      }

      setEvents((prev) => [{ topic, payload, ts: Date.now() }, ...prev].slice(0, 40));
    });

    return () => {
      client.end(true);
    };
  }, []);

  const latestFinal = finals[0] || null;

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
      timestamp: nowTs(),
    });
    publish('system/brain/load/qwen', { source: 'dashboard', timestamp: nowTs() });
  }

  function requestVisionAnalysis() {
    publish('perception/vision/request_analysis', {
      request_id: `dash-${Date.now()}`,
      frame_hint: 'manual_dashboard_request',
      timestamp: nowTs(),
    });
  }

  function setAuditOverride(enabled) {
    setOverrideAudit(enabled);
    publish('system/audit/override', {
      enabled,
      source: 'dashboard',
      timestamp: nowTs(),
    });
  }

  function sendEngineeringFeedback(artifact, value, comment = '') {
    if (!artifact?.artifact_id) return;
    publish('cognition/engineering/feedback', {
      artifact_id: artifact.artifact_id,
      feedback_type: 'explicit',
      feedback_value: value,
      comment,
      user_id: 'dashboard',
      timestamp: nowTs(),
    });

    if (lastRagInteractionId) {
      publish('cognition/rag/feedback', {
        interaction_id: lastRagInteractionId,
        feedback_type: 'explicit',
        feedback_value: value,
        user_id: 'dashboard',
      });
    }
  }

  function sendApproval(decision) {
    if (!latestFinal?.artifact_id) return;
    publish('action/engineering/approval', {
      artifact_id: latestFinal.artifact_id,
      decision,
      comment: approvalComment.trim(),
      user_id: 'dashboard',
      timestamp: nowTs(),
    });

    if (decision === 'aprobar') {
      sendEngineeringFeedback(latestFinal, 1, approvalComment.trim());
      setApprovalComment('');
      return;
    }

    if (decision === 'corregir') {
      sendEngineeringFeedback(latestFinal, -1, approvalComment.trim());
    }
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
            <button className="danger" onClick={emergencyStop}>Parada de emergencia</button>
            <button onClick={requestVisionAnalysis}>Analizar vision</button>
          </div>
        </article>

        <article className="panel">
          <h2>Controles RLHF</h2>
          <label className="toggle-line">
            <input
              type="checkbox"
              checked={overrideAudit}
              onChange={(event) => setAuditOverride(event.target.checked)}
            />
            <span>Override manual de auditoria DeepSeek</span>
          </label>
          <div className="stats">
            <div>Ultimo artifact: {latestFinal?.artifact_id || 'n/a'}</div>
            <div>Borradores recibidos: {drafts.length}</div>
            <div>Resultados finales: {finals.length}</div>
            <div>RAG interaction_id: {lastRagInteractionId || 'n/a'}</div>
          </div>
          <textarea
            className="comment-box"
            placeholder="Comentario de correccion (ground truth del usuario)"
            value={approvalComment}
            onChange={(event) => setApprovalComment(event.target.value)}
          />
          <div className="actions">
            <button className="ok" onClick={() => sendApproval('aprobar')}>APROBAR</button>
            <button className="danger" onClick={() => sendApproval('corregir')}>CORREGIR</button>
          </div>
        </article>

        <article className="panel">
          <h2>Thought monitor</h2>
          <div className="feed">
            {thoughts.length === 0 && <p>No audit traces yet.</p>}
            {thoughts.map((item, idx) => (
              <div key={`${item.timestamp}-${idx}`} className="card">
                <p>{shortText(item.audit_summary, 220)}</p>
                <p>Override: {item.override ? 'si' : 'no'}</p>
                <p>Cambios obligatorios: {Array.isArray(item.mandatory_changes) ? item.mandatory_changes.length : 0}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="panel full-width">
          <h2>Respuestas de ingenieria</h2>
          <div className="feed">
            {finals.length === 0 && <p>No hay respuestas finales aun.</p>}
            {finals.map((item) => (
              <div key={`${item.artifact_id || item.timestamp}`} className="card mono">
                <strong>{item.artifact_id || 'artifact-sin-id'}</strong>
                <p>Prompt: {shortText(item.prompt, 200)}</p>
                <pre>{shortText(item.result, 1200)}</pre>
                <div className="actions">
                  <button onClick={() => sendEngineeringFeedback(item, 1)}>+1</button>
                  <button className="danger" onClick={() => sendEngineeringFeedback(item, -1)}>-1</button>
                </div>
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
