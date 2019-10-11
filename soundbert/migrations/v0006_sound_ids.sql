ALTER TABLE sounds
    DROP CONSTRAINT sounds_pkey;

ALTER TABLE sounds
    ADD id SERIAL;

ALTER TABLE sounds
    ADD CONSTRAINT sounds_pkey
        PRIMARY KEY (id);

CREATE UNIQUE INDEX sounds_guild_id_name_uindex
    ON sounds (guild_id, name);

