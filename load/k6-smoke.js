import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export const options = {
  vus: 3,
  duration: '1m',
  thresholds: {
    http_req_failed: ['rate<0.20'],
    http_req_duration: ['p(95)<2000'],
  },
};

export default function () {
  const responses = [
    http.get(`${BASE_URL}/`),
    http.get(`${BASE_URL}/shop`),
    http.get(`${BASE_URL}/api/products`),
  ];
  for (const response of responses) {
    check(response, { 'status is not 5xx': (r) => r.status < 500 });
  }
  sleep(1);
}
