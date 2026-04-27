import fs from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import process from "node:process";
import { WebSocket } from "ws";

const argv = process.argv.slice(2);
const profileArgIndex = argv.indexOf("--profile");
const profile = profileArgIndex >= 0 ? argv[profileArgIndex + 1] : (process.env.PROFILE || "baseline");
const seed = Number(process.env.SEED || 424242);

const currentFile = fileURLToPath(import.meta.url);
const rootDir = path.resolve(path.join(path.dirname(currentFile), "..", ".."));
const profilesPath = path.join(rootDir, "loadtest", "config", "profiles.json");
const profiles = JSON.parse(fs.readFileSync(profilesPath, "utf8"));
const wsProfile = profiles.ws[profile] || profiles.ws.baseline;
const geo = profiles.geo;

const apiBase = (process.env.API_BASE || "http://localhost:8000").replace(/\/$/, "");
const wsBase = (process.env.WS_BASE || apiBase.replace(/^http/i, "ws")).replace(/\/$/, "");

const resultsDir = path.join(rootDir, "loadtest", "results");
fs.mkdirSync(resultsDir, { recursive: true });

function nowMs() {
  return Date.now();
}

function xorshift32(n) {
  let x = n | 0;
  x ^= x << 13;
  x ^= x >>> 17;
  x ^= x << 5;
  return (x >>> 0) / 4294967296;
}

let prngState = seed | 0;

function nextRandom() {
  prngState ^= prngState << 13;
  prngState ^= prngState >>> 17;
  prngState ^= prngState << 5;
  return (prngState >>> 0) / 4294967296;
}

function randomInRange(min, max, salt) {
  const r = xorshift32((seed + salt + Math.floor(nextRandom() * 1000000)) | 0);
  return min + (max - min) * r;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function postJson(url, body, token = null) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }

  return { status: res.status, data };
}

async function ensureUserAndToken({ email, password, role, hospitalId = null }) {
  const registerPayload = {
    email,
    password,
    role,
  };
  if (hospitalId) registerPayload.hospital_id = hospitalId;

  const reg = await postJson(`${apiBase}/api/auth/register`, registerPayload);
  if (![201, 400].includes(reg.status)) {
    throw new Error(`Register failed for ${email}: ${reg.status}`);
  }

  const login = await postJson(`${apiBase}/api/auth/login`, { email, password });
  if (login.status !== 200 || !login.data?.access_token) {
    throw new Error(`Login failed for ${email}: ${login.status}`);
  }

  return login.data.access_token;
}

function dispatchPayload(caseIndex) {
  const conditionList = ["cardiac_arrest", "respiratory", "trauma", "stroke", "fracture"];
  const severityList = ["moderate", "high", "critical"];

  const lat = Number(randomInRange(geo.latMin, geo.latMax, caseIndex * 17).toFixed(6));
  const lng = Number(randomInRange(geo.lngMin, geo.lngMax, caseIndex * 31).toFixed(6));

  return {
    condition: conditionList[caseIndex % conditionList.length],
    severity: severityList[caseIndex % severityList.length],
    ambulance_lat: lat,
    ambulance_lng: lng,
    required_equipment: ["ventilator"],
    important_equipment: ["ecg"],
    optional_equipment: ["blood_bank"],
    ambulance_equipment: ["oxygen", "defibrillator", "ventilator"],
    vitals: {
      oxygen: 90 + (caseIndex % 6),
      pulse: 98 + (caseIndex % 35),
      systolic: 88 + (caseIndex % 22),
      diastolic: 58 + (caseIndex % 18),
    },
    notes: `ws_seed_case_${caseIndex}`,
  };
}

async function seedDispatchCases(seedCaseCount, ambulanceTokens) {
  const seeded = [];
  let cursor = 0;

  while (seeded.length < seedCaseCount && cursor < seedCaseCount * 4) {
    const token = ambulanceTokens[cursor % ambulanceTokens.length];
    const payload = dispatchPayload(cursor);
    const res = await postJson(`${apiBase}/api/dispatch/`, payload, token);

    if (res.status === 200 && res.data?.case_id && res.data?.hospital_id) {
      seeded.push({
        caseId: Number(res.data.case_id),
        hospitalId: Number(res.data.hospital_id),
        publisherToken: token,
        baseLat: payload.ambulance_lat,
        baseLng: payload.ambulance_lng,
      });
    }

    cursor += 1;
    await sleep(40);
  }

  if (!seeded.length) {
    throw new Error("No dispatch cases could be seeded. Check data availability and auth.");
  }

  return seeded;
}

function percentile(values, p) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor((p / 100) * sorted.length)));
  return sorted[idx];
}

function makeMetrics() {
  return {
    startedAt: new Date().toISOString(),
    profile,
    apiBase,
    wsBase,
    wsConnectAttempts: 0,
    wsConnectSuccess: 0,
    wsConnectFail: 0,
    wsDisconnects: 0,
    wsReconnects: 0,
    wsErrors: 0,
    wsMessagesReceived: 0,
    wsMessagesSent: 0,
    chatPostsOk: 0,
    chatPostsFailed: 0,
    statusMessagesSent: 0,
    fanoutDelaysMs: [],
    fanoutDelivered: 0,
    fanoutDropped: 0,
    outOfOrder: 0,
    pendingTimeouts: 0,
    statusCodeHistogram: {},
  };
}

function incrementHistogram(metrics, status) {
  const key = String(status);
  metrics.statusCodeHistogram[key] = (metrics.statusCodeHistogram[key] || 0) + 1;
}

function wsUrl(caseId, token) {
  return `${wsBase}/ws/track/${caseId}?token=${encodeURIComponent(token)}`;
}

function createTrackedSocket({ role, caseCtx, token, metrics, pendingFanout, sequenceState }) {
  return new Promise((resolve, reject) => {
    metrics.wsConnectAttempts += 1;

    const socket = new WebSocket(wsUrl(caseCtx.caseId, token));

    const state = {
      role,
      caseId: caseCtx.caseId,
      baseLat: caseCtx.baseLat ?? geo.defaultCenterLat,
      baseLng: caseCtx.baseLng ?? geo.defaultCenterLng,
      token,
      socket,
      alive: false,
      lastSeqSeen: -1,
      reconnecting: false,
    };

    const timeout = setTimeout(() => {
      try {
        socket.terminate();
      } catch {
        // no-op
      }
      metrics.wsConnectFail += 1;
      reject(new Error(`WS timeout (${role}) case ${caseCtx.caseId}`));
    }, 6000);

    socket.on("open", () => {
      clearTimeout(timeout);
      state.alive = true;
      metrics.wsConnectSuccess += 1;
      resolve(state);
    });

    socket.on("message", (raw) => {
      metrics.wsMessagesReceived += 1;
      let msg;
      try {
        msg = JSON.parse(String(raw));
      } catch {
        return;
      }

      if (msg.type === "position") {
        const lat = Number(msg.lat);
        const lng = Number(msg.lng);
        const seq = Number(sequenceState.decodeSeq(lat, lng));

        if (Number.isFinite(seq) && seq < state.lastSeqSeen) {
          metrics.outOfOrder += 1;
        }
        if (Number.isFinite(seq)) {
          state.lastSeqSeen = Math.max(state.lastSeqSeen, seq);
        }

        const key = `${caseCtx.caseId}:${lat.toFixed(6)}:${lng.toFixed(6)}`;
        const sentAt = pendingFanout.get(key);
        if (sentAt) {
          pendingFanout.delete(key);
          metrics.fanoutDelivered += 1;
          metrics.fanoutDelaysMs.push(nowMs() - sentAt);
        }
      }

      if (msg.type === "error") {
        metrics.wsErrors += 1;
      }
    });

    socket.on("close", () => {
      if (state.alive) {
        metrics.wsDisconnects += 1;
      }
      state.alive = false;
    });

    socket.on("error", () => {
      metrics.wsErrors += 1;
    });
  });
}

function makeSequenceEncoder() {
  return {
    encode(baseLat, baseLng, seq) {
      const lat = Number((baseLat + (seq % 90) * 0.00001).toFixed(6));
      const lng = Number((baseLng + (seq % 70) * 0.00001).toFixed(6));
      return { lat, lng };
    },
    decodeSeq(lat, lng) {
      const latTail = Math.round((lat - Math.floor(lat)) * 1000000) % 100;
      const lngTail = Math.round((lng - Math.floor(lng)) * 1000000) % 100;
      return latTail * 100 + lngTail;
    },
  };
}

async function run() {
  const metrics = makeMetrics();
  const sequenceState = makeSequenceEncoder();

  const ambulanceAuthUsers = Math.max(20, wsProfile.seedCaseCount);
  const ambulanceTokens = [];

  for (let i = 0; i < ambulanceAuthUsers; i += 1) {
    const token = await ensureUserAndToken({
      email: `loadtest.ws.amb.${profile}.${i}@example.com`,
      password: "Pass123!load",
      role: "ambulance",
    });
    ambulanceTokens.push(token);
  }

  const cases = await seedDispatchCases(wsProfile.seedCaseCount, ambulanceTokens);

  const hospitalTokenById = new Map();
  for (let i = 0; i < cases.length; i += 1) {
    const hospitalId = cases[i].hospitalId;
    if (!hospitalTokenById.has(hospitalId)) {
      const token = await ensureUserAndToken({
        email: `loadtest.ws.hosp.${profile}.${hospitalId}@example.com`,
        password: "Pass123!load",
        role: "hospital",
        hospitalId,
      });
      hospitalTokenById.set(hospitalId, token);
    }
  }

  const sockets = [];
  const pendingFanout = new Map();
  const listenerPool = [];

  for (let i = 0; i < cases.length; i += 1) {
    const caseCtx = cases[i];

    const publisher = await createTrackedSocket({
      role: "publisher",
      caseCtx,
      token: caseCtx.publisherToken,
      metrics,
      pendingFanout,
      sequenceState,
    });
    sockets.push(publisher);

    const hospitalToken = hospitalTokenById.get(caseCtx.hospitalId);

    for (let l = 0; l < wsProfile.listenersPerCase; l += 1) {
      const token = l % 2 === 0 ? hospitalToken : caseCtx.publisherToken;
      const listener = await createTrackedSocket({
        role: "listener",
        caseCtx,
        token,
        metrics,
        pendingFanout,
        sequenceState,
      });
      sockets.push(listener);
      listenerPool.push(listener);
      await sleep(Math.max(5, Math.floor(1000 / Math.max(1, wsProfile.connectRampPerSec))));
    }
  }

  let running = true;
  const stopAt = nowMs() + wsProfile.durationSec * 1000;

  const publisherIntervals = sockets
    .filter((s) => s.role === "publisher")
    .map((pub, index) => {
      let seq = 0;

      return setInterval(() => {
        if (!running || !pub.alive || pub.socket.readyState !== WebSocket.OPEN) return;
        seq += 1;

        const coords = sequenceState.encode(pub.baseLat, pub.baseLng, seq);

        const lat = Number((Math.max(geo.latMin, Math.min(geo.latMax, coords.lat)) || geo.defaultCenterLat).toFixed(6));
        const lng = Number((Math.max(geo.lngMin, Math.min(geo.lngMax, coords.lng)) || geo.defaultCenterLng).toFixed(6));

        const key = `${pub.caseId}:${lat.toFixed(6)}:${lng.toFixed(6)}`;
        pendingFanout.set(key, nowMs());

        try {
          pub.socket.send(JSON.stringify({ type: "ping", lat, lng, speed_kmh: 35 + (index % 30) }));
          metrics.wsMessagesSent += 1;
        } catch {
          metrics.wsErrors += 1;
        }
      }, wsProfile.pingIntervalMs);
    });

  const statusIntervals = sockets
    .filter((s) => s.role === "publisher")
    .map((pub, idx) => setInterval(() => {
      if (!running || !pub.alive || pub.socket.readyState !== WebSocket.OPEN) return;
      const nextStatus = idx % 2 === 0 ? "en_route" : "on_scene";
      try {
        pub.socket.send(JSON.stringify({ type: "status", status: nextStatus }));
        metrics.statusMessagesSent += 1;
        metrics.wsMessagesSent += 1;
      } catch {
        metrics.wsErrors += 1;
      }
    }, wsProfile.statusIntervalMs));

  const chatIntervals = cases.map((caseCtx, i) => setInterval(async () => {
    if (!running) return;
    const token = caseCtx.publisherToken;
    const res = await postJson(
      `${apiBase}/api/cases/${caseCtx.caseId}/messages`,
      { body: `loadtest chat ping ${i}-${nowMs()}` },
      token
    );
    incrementHistogram(metrics, res.status);
    if (res.status === 201) {
      metrics.chatPostsOk += 1;
    } else {
      metrics.chatPostsFailed += 1;
    }
  }, wsProfile.chatIntervalMs));

  const timeoutWatcher = setInterval(() => {
    const expireBefore = nowMs() - 5000;
    for (const [key, ts] of pendingFanout.entries()) {
      if (ts < expireBefore) {
        pendingFanout.delete(key);
        metrics.pendingTimeouts += 1;
        metrics.fanoutDropped += 1;
      }
    }
  }, 1000);

  const churnInterval = setInterval(async () => {
    if (!running || !listenerPool.length) return;

    const churnCount = Math.max(1, Math.floor(listenerPool.length * wsProfile.churnPercent));
    for (let i = 0; i < churnCount; i += 1) {
      const idx = Math.floor(Math.random() * listenerPool.length);
      const listener = listenerPool[idx];
      if (!listener) continue;

      try {
        listener.socket.close();
      } catch {
        // no-op
      }

      metrics.wsReconnects += 1;
      await sleep(50);

      try {
        const replacement = await createTrackedSocket({
          role: "listener",
          caseCtx: { caseId: listener.caseId },
          token: listener.token,
          metrics,
          pendingFanout,
          sequenceState,
        });
        listenerPool[idx] = replacement;
      } catch {
        metrics.wsConnectFail += 1;
      }
    }
  }, wsProfile.churnIntervalMs);

  while (nowMs() < stopAt) {
    await sleep(500);
  }

  running = false;

  [
    ...publisherIntervals,
    ...statusIntervals,
    ...chatIntervals,
    timeoutWatcher,
    churnInterval,
  ].forEach((timer) => clearInterval(timer));

  for (const sock of [...sockets, ...listenerPool]) {
    try {
      sock.socket.close();
    } catch {
      // no-op
    }
  }

  metrics.finishedAt = new Date().toISOString();
  metrics.runtimeSec = wsProfile.durationSec;

  const delays = metrics.fanoutDelaysMs;
  metrics.fanoutDelayMs = {
    p50: percentile(delays, 50),
    p95: percentile(delays, 95),
    p99: percentile(delays, 99),
    max: delays.length ? Math.max(...delays) : null,
    count: delays.length,
  };

  metrics.wsConnectSuccessRate = metrics.wsConnectAttempts
    ? metrics.wsConnectSuccess / metrics.wsConnectAttempts
    : 0;

  metrics.deliverySuccessRate =
    metrics.fanoutDelivered + metrics.fanoutDropped > 0
      ? metrics.fanoutDelivered / (metrics.fanoutDelivered + metrics.fanoutDropped)
      : 0;

  const summaryPath = path.join(resultsDir, `ws-${profile}-summary.json`);
  fs.writeFileSync(summaryPath, JSON.stringify(metrics, null, 2));

  const csvPath = path.join(resultsDir, `ws-${profile}-fanout.csv`);
  const csvLines = ["delay_ms"];
  for (const value of delays) csvLines.push(String(value));
  fs.writeFileSync(csvPath, csvLines.join("\n"));

  console.log(JSON.stringify({
    profile,
    summaryPath,
    csvPath,
    wsConnectSuccessRate: metrics.wsConnectSuccessRate,
    deliverySuccessRate: metrics.deliverySuccessRate,
    fanoutDelayMs: metrics.fanoutDelayMs,
    outOfOrder: metrics.outOfOrder,
    dropped: metrics.fanoutDropped,
    reconnects: metrics.wsReconnects,
  }, null, 2));
}

run().catch((err) => {
  console.error("WS load test failed:", err.message);
  process.exitCode = 1;
});
