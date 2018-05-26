CREATE TABLE IF NOT EXISTS guild
(
  id BIGINT PRIMARY KEY
);

CREATE TABLE sounds
(
  guild_id BIGINT            NOT NULL
    CONSTRAINT sounds_guild_id_fk
    REFERENCES guild
    ON UPDATE CASCADE
    ON DELETE CASCADE,
  filename VARCHAR(128)      NOT NULL,
  name     VARCHAR           NOT NULL,
  played   INTEGER DEFAULT 0 NOT NULL,
  stopped  INTEGER DEFAULT 0 NOT NULL,
  PRIMARY KEY (guild_id, filename)
);
