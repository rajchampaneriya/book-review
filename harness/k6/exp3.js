// Experiment 3 load script. Env: BASE_URL, STACK, VARIANT (naive|v2), FAULT_RATE
// (0, 0.01, 0.05), RUN_ID, RUN, RATE (default 100/s), TOTAL (default 10000),
// TIMEOUT (default 1s), MAX_ATTEMPTS (default 3), BACKOFF_MS (default 200).
//
// Logical request i = exec.scenario.iterationInTest; client_ref = RUN_ID-i and,
// for v2, the same value is the Idempotency-Key. Request i is faulted (client
// timeout on an already-committed booking) if ((i * 2654435761) % 10000) <
// FAULT_RATE * 10000, on its first attempt only. Retries reuse body and key.
import http from 'k6/http';
import exec from 'k6/execution';
import { Counter, Trend } from 'k6/metrics';
import { sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL;
const STACK = __ENV.STACK;
const VARIANT = __ENV.VARIANT;
const RUN_ID = __ENV.RUN_ID;
const RUN = __ENV.RUN;
const FAULT_RATE = parseFloat(__ENV.FAULT_RATE || '0');
const RATE = parseInt(__ENV.RATE || '100', 10);
const TOTAL = parseInt(__ENV.TOTAL || '10000', 10);
const TIMEOUT = __ENV.TIMEOUT || '1s';
const MAX_ATTEMPTS = parseInt(__ENV.MAX_ATTEMPTS || '3', 10);
const BACKOFF_MS = parseFloat(__ENV.BACKOFF_MS || '200');

const logical_requests = new Counter('logical_requests');
const attempts = new Counter('attempts');
const timeouts = new Counter('timeouts');
const gave_up = new Counter('gave_up');
const successful_attempt_duration = new Trend('successful_attempt_duration');

export const options = {
  discardResponseBodies: true,
  scenarios: {
    exp3: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      duration: `${TOTAL / RATE}s`,
      preAllocatedVUs: Math.max(200, RATE * 4),
      maxVUs: Math.max(500, RATE * 8),
    },
  },
};

const PATHS = { naive: '/naive/bookings', v2: '/v2/bookings' };
const path = PATHS[VARIANT];

export default function () {
  const i = exec.scenario.iterationInTest;
  const clientRef = `${RUN_ID}-${i}`;
  const body = JSON.stringify({
    client_ref: clientRef,
    session_id: 's-42',
    dog_id: 'd-7',
    owner_id: 'o-9',
    deposit_cents: 2500,
  });
  const faultedFirstAttempt = ((i * 2654435761) % 10000) < FAULT_RATE * 10000;

  logical_requests.add(1);
  for (let attemptNo = 1; attemptNo <= MAX_ATTEMPTS; attemptNo++) {
    const headers = { 'Content-Type': 'application/json' };
    if (VARIANT === 'v2') headers['Idempotency-Key'] = clientRef;
    if (attemptNo === 1 && faultedFirstAttempt) headers['X-Fault'] = 'hold-after-commit';

    attempts.add(1);
    const response = http.post(`${BASE_URL}${path}`, body, { headers, timeout: TIMEOUT });

    if (response.status >= 200 && response.status < 300) {
      successful_attempt_duration.add(response.timings.duration);
      return;
    }
    if (response.status === 0) timeouts.add(1);
    const retryable = response.status === 0 || response.status >= 500 || response.status === 409;
    if (!retryable || attemptNo === MAX_ATTEMPTS) {
      gave_up.add(1);
      return;
    }
    sleep(BACKOFF_MS / 1000);
  }
}

export function handleSummary(data) {
  return {
    [`results/exp3/raw/${STACK}_${VARIANT}_f${FAULT_RATE}_r${RUN}.json`]: JSON.stringify(data),
  };
}
