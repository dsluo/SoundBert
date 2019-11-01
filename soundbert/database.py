from sqlalchemy import Integer, Table, Column, MetaData, String, Text, BigInteger, DateTime, Float, ForeignKey, Boolean, \
    Index, text

metadata = MetaData()

guilds = Table(
        'guilds',
        metadata,
        Column('id', BigInteger(), primary_key=True),
        Column('prefix', String(20)),
        Column('soundmaster', BigInteger()),
        Column('soundplayer', BigInteger())
)

sounds = Table(
        'sounds',
        metadata,
        Column('id', Integer(), primary_key=True),
        Column('filename', String(128), nullable=False),
        Column('played', Integer(), nullable=False, server_default=text('0')),
        Column('stopped', Integer(), nullable=False, server_default=text('0')),
        Column('source', Text()),
        Column('uploader', BigInteger()),
        Column('upload_time', DateTime()),
        Column('length', Float(), nullable=False)
)

sound_names = Table(
        'sound_names',
        metadata,
        Column('id', Integer(), primary_key=True),
        Column('sound_id', Integer(), ForeignKey('sounds.id', ondelete='CASCADE'), nullable=False),
        Column('guild_id', Integer(), ForeignKey('guilds.id', ondelete='CASCADE'), nullable=False),
        Column('name', String(), index=True),
        Column('is_alias', Boolean(), default=True, server_default=text('false')),
        Index('sound_names_sound_id_guild_id_name_uindex', 'sound_id', 'guild_id', text('lower(name)'), unique=True)
)
