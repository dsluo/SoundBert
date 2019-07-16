create table clips
(
	guild_id bigint not null
		constraint clips_guilds_id_fk
			references guilds
				on update cascade on delete cascade,
	name varchar not null,
    content varchar not null,
	pasted integer default 0 not null,
	uploader bigint,
	upload_time timestamp,
	constraint clips_pk
		primary key (guild_id, name)
);
