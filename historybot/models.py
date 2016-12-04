import sqlalchemy as sa

metadata = sa.MetaData()


channels_table = sa.Table('channels', metadata,
    sa.Column('id', sa.String(10), primary_key=True),
    sa.Column('name', sa.String(100))
)

users_table = sa.Table('users', metadata,
    sa.Column('id', sa.String(10), primary_key=True),
    sa.Column('name', sa.String(10)),
)

messages_table = sa.Table('messages', metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('channel_id', None, sa.ForeignKey('channels.id')),
    sa.Column('user_id', None, sa.ForeignKey('users.id')),
    sa.Column('text', sa.Text()),
    sa.Column('timestamp', sa.DateTime()),
)
