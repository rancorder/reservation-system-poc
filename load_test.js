import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 50 },
    { duration: '20s', target: 100 },
    { duration: '10s', target: 0 },
  ],
};

export default function () {
  const baseUrl = 'http://localhost:8000';
  
  // Redis分散ロック
  const agentId = `agent_${Math.floor(Math.random() * 10) + 1}`;
  const res1 = http.post(`/reserve/agent/${agentId}`);
  check(res1, {
    'Redis lock: 200 or 409': (r) => r.status === 200 || r.status === 409,
  });

  // 楽観的ロック
  const slotId = Math.floor(Math.random() * 10) + 1;
  const res2 = http.post(`/reserve/slot/${slotId}/optimistic?version=0`);
  check(res2, {
    'Optimistic: 200 or 409': (r) => r.status === 200 || r.status === 409,
  });

  // 悲観的ロック
  const slotId2 = Math.floor(Math.random() * 10) + 1;
  const res3 = http.post(`/reserve/slot/${slotId2}/pessimistic`);
  check(res3, {
    'Pessimistic: 200 or 409': (r) => r.status === 200 || r.status === 409,
  });

  sleep(0.1);
}
