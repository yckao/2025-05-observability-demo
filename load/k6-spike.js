import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export const options = {
  stages: [
    { duration: '20s', target: 5 },
    { duration: '20s', target: 50 },
    { duration: '40s', target: 50 },
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.50'],
  },
};

export default function () {
  const response = http.get(`${BASE_URL}/shop`);
  check(response, { 'response received': (r) => r.status > 0 });
  sleep(0.2);
}
