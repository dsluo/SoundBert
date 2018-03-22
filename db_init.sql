CREATE TABLE sounds
(
  guild_id BIGINT            NOT NULL,
  filename VARCHAR(128)      NOT NULL,
  name     VARCHAR           NOT NULL,
  played   INTEGER DEFAULT 0 NOT NULL,
  stopped  INTEGER DEFAULT 0 NOT NULL,
  PRIMARY KEY (guild_id, filename)
);
