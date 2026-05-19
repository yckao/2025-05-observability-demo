CREATE DATABASE IF NOT EXISTS observability_demo;

USE observability_demo;

CREATE TABLE IF NOT EXISTS products (
  id INT PRIMARY KEY,
  name STRING NOT NULL,
  price_cents INT NOT NULL,
  stock INT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  total_cents INT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

UPSERT INTO products (id, name, price_cents, stock) VALUES
  (1, 'Observability Notebook', 1299, 200),
  (2, 'Trace Context Hoodie', 4999, 80),
  (3, 'Latency Lab Mug', 1899, 120),
  (4, 'Golden Signals Poster', 999, 300);
