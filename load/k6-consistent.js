import exec from 'k6/execution';
import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = (__ENV.BASE_URL || 'http://localhost:8080').replace(/\/$/, '');
const TRAFFIC_DURATION = __ENV.TRAFFIC_DURATION || '30m';
const DEFAULT_MAX_VUS = parsePositiveInteger('MAX_VUS', 50);

function parsePositiveInteger(name, fallback) {
  const value = Number.parseInt(__ENV[name] || `${fallback}`, 10);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function parseRate(name, fallback) {
  const value = Number.parseInt(__ENV[name] || `${fallback}`, 10);
  return Number.isFinite(value) && value > 0 ? value : 0;
}

function preAllocatedVus(ratePerMinute) {
  const configured = Number.parseInt(__ENV.PREALLOCATED_VUS || '', 10);
  if (Number.isFinite(configured) && configured > 0) {
    return configured;
  }
  return Math.max(1, Math.ceil(ratePerMinute / 30));
}

function addScenario(scenarios, name, envName, defaultRate, execName) {
  const rate = parseRate(envName, defaultRate);
  if (rate === 0) {
    return;
  }

  const preAllocated = preAllocatedVus(rate);

  scenarios[name] = {
    executor: 'constant-arrival-rate',
    rate,
    timeUnit: '1m',
    duration: TRAFFIC_DURATION,
    preAllocatedVUs: preAllocated,
    maxVUs: Math.max(preAllocated, DEFAULT_MAX_VUS),
    exec: execName,
    tags: {
      traffic_profile: 'consistent',
      flow: name,
    },
  };
}

const scenarios = {};
addScenario(scenarios, 'home', 'HOME_PER_MIN', 20, 'home');
addScenario(scenarios, 'shop_journey', 'SHOP_PER_MIN', 30, 'shopJourney');
addScenario(scenarios, 'products_api', 'PRODUCTS_PER_MIN', 20, 'productsApi');
addScenario(scenarios, 'checkout_api', 'CHECKOUT_PER_MIN', 10, 'checkoutApi');
addScenario(scenarios, 'orders_api', 'ORDERS_PER_MIN', 10, 'ordersApi');
addScenario(scenarios, 'health', 'HEALTH_PER_MIN', 6, 'health');

if (Object.keys(scenarios).length === 0) {
  scenarios.health = {
    executor: 'constant-arrival-rate',
    rate: 1,
    timeUnit: '1m',
    duration: TRAFFIC_DURATION,
    preAllocatedVUs: 1,
    maxVUs: Math.max(1, DEFAULT_MAX_VUS),
    exec: 'health',
    tags: {
      traffic_profile: 'consistent',
      flow: 'health',
    },
  };
}

export const options = {
  scenarios,
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  userAgent: 'observability-demo-traffic-generator/1.0',
};

function requestParams(flow) {
  return {
    headers: {
      'X-Demo-Traffic': 'consistent',
    },
    tags: {
      flow,
    },
  };
}

function checkCompleted(response) {
  check(response, {
    'request completed': (r) => r.status > 0,
  });
}

export function home() {
  checkCompleted(http.get(`${BASE_URL}/`, requestParams('home')));
}

export function shopJourney() {
  checkCompleted(http.get(`${BASE_URL}/shop`, requestParams('shop_journey')));
}

export function productsApi() {
  checkCompleted(http.get(`${BASE_URL}/api/products`, requestParams('products_api')));
}

export function checkoutApi() {
  const productId = (exec.scenario.iterationInTest % 4) + 1;
  const params = requestParams('checkout_api');
  checkCompleted(
    http.post(
      `${BASE_URL}/api/checkout`,
      JSON.stringify({ product_id: productId }),
      {
        ...params,
        headers: {
          ...params.headers,
          'Content-Type': 'application/json',
        },
      },
    ),
  );
}

export function ordersApi() {
  checkCompleted(http.get(`${BASE_URL}/api/orders`, requestParams('orders_api')));
}

export function health() {
  checkCompleted(http.get(`${BASE_URL}/health`, requestParams('health')));
  checkCompleted(http.get(`${BASE_URL}/api/health`, requestParams('health')));
}
