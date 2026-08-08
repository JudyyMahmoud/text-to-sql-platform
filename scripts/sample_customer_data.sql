-- Sample "customer" business database used to test the Text-to-SQL feature.
-- This is loaded automatically into the sample_customer_db container.

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    country VARCHAR(100),
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(30) NOT NULL,
    order_date DATE NOT NULL
);

CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    invoice_value NUMERIC(12, 2) NOT NULL,
    issued_date DATE NOT NULL
);

INSERT INTO customers (name, country, email) VALUES
    ('Acme Corp', 'USA', 'contact@acme.com'),
    ('Globex', 'Germany', 'info@globex.com'),
    ('Nile Traders', 'Egypt', 'sales@niletraders.com'),
    ('Umbrella Inc', 'UK', 'hello@umbrella.com');

INSERT INTO orders (customer_id, amount, status, order_date) VALUES
    (1, 15000.00, 'completed', '2026-01-15'),
    (1, 8200.50, 'completed', '2026-03-02'),
    (2, 42000.00, 'pending', '2026-04-10'),
    (3, 9600.75, 'completed', '2026-02-20'),
    (4, 3100.00, 'cancelled', '2026-05-01');

INSERT INTO invoices (order_id, invoice_value, issued_date) VALUES
    (1, 15000.00, '2026-01-16'),
    (2, 8400.00, '2026-03-03'),
    (4, 9600.75, '2026-02-21');
