alter table sounds
    drop constraint sounds_pkey;

alter table sounds
    add constraint sounds_pkey
        primary key (guild_id, name);
