import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '4m', target: 10 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.30'],
    http_req_duration: ['p(95)<3000'],
  },
};

export default function () {
  const flow = Math.random();
  let response;
  if (flow < 0.50) {
    response = http.get(`${BASE_URL}/shop`);
  } else if (flow < 0.80) {
    response = http.get(`${BASE_URL}/api/products`);
  } else {
    response = http.get(`${BASE_URL}/api/orders`);
  }
  check(response, { 'status is not 5xx': (r) => r.status < 500 });
  sleep(Math.random() * 1.5);
}
