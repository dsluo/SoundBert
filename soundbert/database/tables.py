from sqlalchemy import Integer, Table, Column, MetaData, String, Text, BigInteger, DateTime, Float, ForeignKey, Boolean

metadata = MetaData()

guilds = Table(
    'guilds',
    metadata,
    Column('id', Integer(), primary_key=True),
    Column('prefix', String()),
    Column('soundmaster', BigInteger()),
    Column('soundplayer', BigInteger())
)

sounds = Table(
    'sounds',
    metadata,
    Column('id', Integer(), primary_key=True),
    Column('filename', Text()),
    Column('played', Integer()),
    Column('stopped', Integer()),
    Column('source', Text()),
    Column('uploader', BigInteger()),
    Column('upload_time', DateTime()),
    Column('length', Float())
)

sound_names = Table(
    'sound_names',
    metadata,
    Column('id', Integer(), primary_key=True),
    Column('sound_id', Integer(), ForeignKey('sounds.id')),
    Column('guild_id', Integer(), ForeignKey('guilds.id')),
    Column('name', String()),
    Column('is_alias', Boolean(), default=True)
)
