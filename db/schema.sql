CREATE SCHEMA IF NOT EXISTS {stack};

CREATE TABLE {stack}.bookings (
  id            uuid PRIMARY KEY,
  client_ref    text NOT NULL,       -- measurement only; deliberately NOT unique
  session_id    text NOT NULL,
  dog_id        text NOT NULL,
  owner_id      text NOT NULL,
  deposit_cents integer NOT NULL CHECK (deposit_cents > 0),
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE {stack}.charges (
  id           uuid PRIMARY KEY,
  booking_id   uuid NOT NULL REFERENCES {stack}.bookings(id),
  client_ref   text NOT NULL,
  amount_cents integer NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE {stack}.idempotency_keys (
  key          text PRIMARY KEY,
  request_hash text NOT NULL,
  result       jsonb,                -- the use case's result: booking_id, charge_id, status
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON {stack}.bookings (client_ref);
CREATE INDEX ON {stack}.charges (client_ref);
