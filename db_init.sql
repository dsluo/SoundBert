CREATE TABLE sounds
(
  filename VARCHAR(128)      NOT NULL
    CONSTRAINT table_name_pkey
    PRIMARY KEY,
  name     VARCHAR           NOT NULL,
  played   INTEGER DEFAULT 0 NOT NULL,
  stopped  INTEGER DEFAULT 0 NOT NULL
);

CREATE UNIQUE INDEX table_name_name_uindex
  ON sounds (name);
