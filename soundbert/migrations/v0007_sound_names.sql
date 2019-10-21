-- create new sound_names table
CREATE TABLE sound_names
(
    id       SERIAL
        CONSTRAINT sound_names_pk
            PRIMARY KEY,
    sound_id SERIAL             NOT NULL
        CONSTRAINT sound_names_sounds_id_fk
            REFERENCES sounds
            ON DELETE CASCADE,
    guild_id BIGINT             NOT NULL
        CONSTRAINT sound_names_guilds_id_fk
            REFERENCES guilds
            ON DELETE CASCADE,
    name     VARCHAR            NOT NULL,
    is_alias    BOOL DEFAULT FALSE NOT NULL
);

CREATE UNIQUE INDEX sound_names_sound_id_guild_id_name_uindex
    ON sound_names (sound_id, guild_id, name);

-- copy data from old table
INSERT INTO sound_names(sound_id, guild_id, name)
SELECT id, guild_id, name
FROM sounds
ORDER BY id;

-- remove old columns
DROP INDEX sounds_guild_id_name_uindex;

ALTER TABLE sounds
    DROP COLUMN name;

ALTER TABLE sounds
    DROP CONSTRAINT sounds_guild_id_fk;

ALTER TABLE sounds
    DROP COLUMN guild_id;

