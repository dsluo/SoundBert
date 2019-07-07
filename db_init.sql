CREATE TABLE guilds
(
    id     BIGINT PRIMARY KEY,
    prefix VARCHAR(20)
);

CREATE TABLE sounds
(
    guild_id BIGINT            NOT NULL
        CONSTRAINT sounds_guild_id_fk
            REFERENCES guilds
            ON UPDATE CASCADE
            ON DELETE CASCADE,
    filename VARCHAR(128)      NOT NULL,
    name     VARCHAR           NOT NULL,
    played   INTEGER DEFAULT 0 NOT NULL,
    stopped  INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (guild_id, filename)
);
