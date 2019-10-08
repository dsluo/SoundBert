CREATE TABLE guilds
(
    id     BIGINT NOT NULL
        CONSTRAINT guild_pkey
            PRIMARY KEY,
    prefix VARCHAR(20)
);

CREATE TABLE sounds
(
    guild_id    BIGINT            NOT NULL
        CONSTRAINT sounds_guild_id_fk
            REFERENCES guilds
            ON UPDATE CASCADE ON DELETE CASCADE,
    filename    VARCHAR(128)      NOT NULL,
    name        VARCHAR           NOT NULL,
    played      INTEGER DEFAULT 0 NOT NULL,
    stopped     INTEGER DEFAULT 0 NOT NULL,
    source      TEXT,
    uploader    BIGINT,
    upload_time TIMESTAMP,
    CONSTRAINT sounds_pkey
        PRIMARY KEY (guild_id, name)
);

CREATE TABLE clips
(
    guild_id    BIGINT            NOT NULL
        CONSTRAINT clips_guilds_id_fk
            REFERENCES guilds
            ON UPDATE CASCADE ON DELETE CASCADE,
    name        VARCHAR           NOT NULL,
    pasted      INTEGER DEFAULT 0 NOT NULL,
    uploader    BIGINT,
    upload_time TIMESTAMP,
    content     VARCHAR           NOT NULL,
    CONSTRAINT clips_pk
        PRIMARY KEY (guild_id, name)
);
