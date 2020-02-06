from sqlalchemy import Integer, Table, Column, MetaData, String, Text, BigInteger, DateTime, ForeignKey, Boolean, \
    text, UniqueConstraint, func, Interval

metadata = MetaData()

guilds = Table(
        'guilds',
        metadata,
        Column('id', BigInteger(), primary_key=True),
        Column('prefix', String(), nullable=False),
        Column('soundmaster', BigInteger()),
        Column('soundplayer', BigInteger())
)

sounds = Table(
        'sounds',
        metadata,
        Column('id', Integer(), primary_key=True),
        Column('played', Integer(), server_default='0', nullable=False),
        Column('stopped', Integer(), server_default='0', nullable=False),
        Column('source', Text(), nullable=False),
        Column('uploader', BigInteger(), nullable=False),
        Column('upload_time', DateTime(timezone=True), server_default=func.now(), nullable=False),
        Column('length', Interval(), nullable=False)
)

sound_names = Table(
        'sound_names',
        metadata,
        Column('id', Integer(), primary_key=True),
        Column('sound_id', Integer(), ForeignKey('sounds.id', ondelete='CASCADE'), nullable=False),
        Column('guild_id', Integer(), ForeignKey('guilds.id', ondelete='CASCADE'), nullable=False),
        Column('name', String(collation='case_insensitive'), nullable=False),
        Column('is_alias', Boolean(), server_default=text('false'), nullable=False),
        UniqueConstraint('sound_id', 'guild_id', 'name')
)
