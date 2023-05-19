CREATE TABLE user (
    user_id INTEGER,
    symbols VARCHAR(255),
    name VARCHAR(255),
    shares INTEGER,
    price NUMERIC,
    total INTERGER
);

CREATE TABLE users (
    id INTEGER,
    username TEXT NOT NULL,
    hash TEXT NOT NULL,
    cash NUMERIC NOT NULL DEFAULT 10000.00,
    PRIMARY KEY(id)
);

CREATE UNIQUE INDEX username ON users (username);

CREATE TABLE history (
    id INTEGER,
    symbols VARCHAR(255),
    price INTEGER,
    stocks INTEGER,
    date VARCHAR(255)
);