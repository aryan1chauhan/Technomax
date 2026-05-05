import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const profile = (__ENV.PROFILE || "baseline").toLowerCase();
const apiBase = __ENV.API_BASE || "http://localhost:8000";
const seed = Number(__ENV.SEED || 12345);

const profileConfig = {
  baseline: {
    preAllocatedVUs: 30,
    maxVUs: 80,
    rate: 8,
    timeUnit: "1s",
    duration: "10m",
    thinkMin: 0.15,
    thinkMax: 0.7,
  },
  peak: {
    preAllocatedVUs: 80,
    maxVUs: 220,
    rate: 25,
    timeUnit: "1s",
    duration: "15m",
    thinkMin: 0.1,
    thinkMax: 0.5,
  },
  spike: {
    preAllocatedVUs: 100,
    maxVUs: 300,
    rate: 60,
    timeUnit: "1s",
    duration: "5m",
    thinkMin: 0.05,
    thinkMax: 0.25,
  },
  soak: {
    preAllocatedVUs: 70,
    maxVUs: 180,
    rate: 12,
    timeUnit: "1s",
    duration: "30m",
    thinkMin: 0.12,
    thinkMax: 0.55,
  },
};

const cfg = profileConfig[profile] || profileConfig.baseline;

const dispatchLatency = new Trend("dispatch_latency_ms");
const dispatchOk = new Rate("dispatch_ok_rate");
const dispatchNon2xx = new Rate("dispatch_non_2xx_rate");
const dispatchStatusCount = new Counter("dispatch_status_count");

const headers = {
  "Content-Type": "application/json",
};

const CONDITIONS = [
  "cardiac_arrest",
  "respiratory",
  "trauma",
  "stroke",
  "fracture",
  "chest_pain",
];

const AMBULANCE_EQUIPMENT = ["oxygen", "defibrillator", "ventilator", "ecg"];
const REQUIRED_EQUIPMENT = ["defibrillator", "ventilator", "ecg", "blood_bank", "ct_scan"];

function xorshift32(value) {
  let x = value | 0;
  x ^= x << 13;
  x ^= x >>> 17;
  x ^= x << 5;
  return (x >>> 0) / 4294967296;
}

function randomInRange(min, max, salt) {
  const r = xorshift32(seed + salt + __VU * 100003 + __ITER * 97);
  return min + (max - min) * r;
}

function choose(list, salt) {
  const idx = Math.floor(randomInRange(0, list.length, salt));
  return list[idx % list.length];
}

function intInRange(min, max, salt) {
  return Math.floor(randomInRange(min, max + 1, salt));
}

function makeDispatchPayload() {
  const condition = choose(CONDITIONS, 11);
  const severity = choose(["low", "moderate", "high", "critical"], 17);

  const lat = Number(randomInRange(29.5, 31.5, 23).toFixed(6));
  const lng = Number(randomInRange(77.5, 80.5, 29).toFixed(6));

  const vitals = {
    oxygen: intInRange(82, 99, 31),
    pulse: intInRange(70, 145, 37),
    systolic: intInRange(85, 150, 41),
    diastolic: intInRange(55, 95, 43),
  };

  return {
    condition,
    severity,
    ambulance_lat: lat,
    ambulance_lng: lng,
    required_equipment: [choose(REQUIRED_EQUIPMENT, 47)],
    important_equipment: [choose(REQUIRED_EQUIPMENT, 53)],
    optional_equipment: [choose(REQUIRED_EQUIPMENT, 59)],
    ambulance_equipment: AMBULANCE_EQUIPMENT,
    vitals,
    notes: "loadtest_dispatch_profile_" + profile,
  };
}

function ensureAmbulanceUser(email, password) {
  const loginPayload = JSON.stringify({ email, password });
  let loginRes = http.post(`${apiBase}/api/auth/login`, loginPayload, { headers });

  if (loginRes.status === 200 && loginRes.json("access_token")) {
    return loginRes.json("access_token");
  }

  const regPayload = JSON.stringify({
    email,
    password,
    role: "ambulance",
  });
  const regRes = http.post(`${apiBase}/api/auth/register`, regPayload, { headers });

  check(regRes, {
    "register status is created or duplicate": (r) => r.status === 201 || r.status === 400,
  });

  loginRes = http.post(`${apiBase}/api/auth/login`, loginPayload, { headers });

  check(loginRes, {
    "login returns token": (r) => r.status === 200 && !!loginRes.json("access_token"),
  });

  if (loginRes.status !== 200) {
    return null;
  }

  return loginRes.json("access_token");
}

export function setup() {
  const authUsers = Number(__ENV.AUTH_USERS || Math.max(cfg.maxVUs, 50));
  const tokens = [];

  for (let i = 0; i < authUsers; i += 1) {
    const email = `loadtest.amb.${profile}.${i}@example.com`;
    const password = "Pass123!load";
    const token = ensureAmbulanceUser(email, password);
    if (token) {
      tokens.push(token);
    }
  }

  if (!tokens.length) {
    throw new Error("No auth tokens generated in setup().");
  }

  return { tokens };
}

export const options = {
  setupTimeout: "180s",
  scenarios: {
    dispatch_traffic: {
      executor: "constant-arrival-rate",
      rate: cfg.rate,
      timeUnit: cfg.timeUnit,
      duration: cfg.duration,
      preAllocatedVUs: cfg.preAllocatedVUs,
      maxVUs: cfg.maxVUs,
    },
  },
  thresholds: {
    dispatch_ok_rate: ["rate>0.97"],
    dispatch_non_2xx_rate: [profile === "peak" || profile === "spike" ? "rate<0.03" : "rate<0.01"],
    http_req_duration: [profile === "peak" || profile === "spike" ? "p(95)<1500" : "p(95)<800"],
    http_req_failed: ["rate<0.03"],
  },
};

export default function (data) {
  const token = data.tokens[(__VU + __ITER) % data.tokens.length];
  const payload = JSON.stringify(makeDispatchPayload());

  const res = http.post(`${apiBase}/api/dispatch/`, payload, {
    headers: {
      ...headers,
      Authorization: `Bearer ${token}`,
    },
    tags: { endpoint: "dispatch" },
  });

  dispatchLatency.add(res.timings.duration);
  dispatchStatusCount.add(1, { status: String(res.status) });

  const is2xx = res.status >= 200 && res.status < 300;
  dispatchOk.add(res.status === 200);
  dispatchNon2xx.add(!is2xx);

  check(res, {
    "dispatch accepted or no-match": (r) => r.status === 200 || r.status === 404 || r.status === 409,
  });

  sleep(randomInRange(cfg.thinkMin, cfg.thinkMax, 71));
}

export function handleSummary(summary) {
  const fileBase = `loadtest/results/dispatch-${profile}`;
  return {
    [`${fileBase}-summary.json`]: JSON.stringify(summary, null, 2),
    stdout: JSON.stringify({
      profile,
      metrics: {
        http_req_duration: summary.metrics.http_req_duration,
        http_req_failed: summary.metrics.http_req_failed,
        dispatch_ok_rate: summary.metrics.dispatch_ok_rate,
        dispatch_non_2xx_rate: summary.metrics.dispatch_non_2xx_rate,
      },
    }, null, 2),
  };
}
