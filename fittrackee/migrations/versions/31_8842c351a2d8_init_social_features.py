"""init social features

Revision ID: 8842c351a2d8
Revises: 4e8597c50064
Create Date: 2021-01-10 16:02:43.811023

"""
import os
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

from fittrackee.federation.utils import (
    generate_keys, get_ap_url, remove_url_scheme
)


# revision identifiers, used by Alembic.
revision = '8842c351a2d8'
down_revision = '374a670efe23'
branch_labels = None
depends_on = None

privacy_levels = ENUM(
    'PUBLIC', 'FOLLOWERS_AND_REMOTE', 'FOLLOWERS', 'PRIVATE',
    name='privacy_levels'
)


def upgrade():
    domain_table = op.create_table(
        'domains',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=1000), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_allowed', sa.Boolean(), nullable=False),
        sa.Column('software_name', sa.String(length=255), nullable=True),
        sa.Column('software_version', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # create local domain (even if federation is not enabled)
    domain = remove_url_scheme(os.environ['UI_URL'])
    created_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    op.execute(
        "INSERT INTO domains (name, created_at, is_allowed, software_name)"
        f"VALUES ('{domain}', '{created_at}'::timestamp, True, 'fittrackee')"
    )

    actors_table = op.create_table(
        'actors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('activitypub_id', sa.String(length=255), nullable=False),
        sa.Column('domain_id', sa.Integer(), nullable=False),
        sa.Column(
            'type',
            sa.Enum('APPLICATION', 'GROUP', 'PERSON', name='actor_types'),
            server_default='PERSON',
            nullable=True,
        ),
        sa.Column('preferred_username', sa.String(length=255), nullable=False),
        sa.Column('public_key', sa.String(length=5000), nullable=True),
        sa.Column('private_key', sa.String(length=5000), nullable=True),
        sa.Column('profile_url', sa.String(length=255), nullable=False),
        sa.Column('inbox_url', sa.String(length=255), nullable=False),
        sa.Column('outbox_url', sa.String(length=255), nullable=False),
        sa.Column('followers_url', sa.String(length=255), nullable=False),
        sa.Column('following_url', sa.String(length=255), nullable=False),
        sa.Column('shared_inbox_url', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_fetch_date', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['domain_id'],
            ['domains.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('activitypub_id'),
        sa.UniqueConstraint(
            'domain_id', 'preferred_username', name='domain_username_unique'
        ),
    )
    op.create_table(
        'remote_actors_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('items', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('followers', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('following', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.ForeignKeyConstraint(
            ['actor_id'],
            ['actors.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_remote_actors_stats_actor_id'),
        'remote_actors_stats',
        ['actor_id'],
        unique=True
    )

    op.add_column(
        'users',
        sa.Column('manually_approves_followers', sa.Boolean(),
        nullable=True)
    )
    op.add_column('users', sa.Column('actor_id', sa.Integer(), nullable=True))
    op.add_column(
        'users',
        sa.Column('is_remote', sa.Boolean(),
        nullable=True)
    )
    op.create_unique_constraint('users_actor_id_key', 'users', ['actor_id'])
    op.create_foreign_key(
        'users_actor_id_fkey', 'users', 'actors', ['actor_id'], ['id']
    )
    op.drop_constraint('users_username_key', 'users', type_='unique')
    # user email, password and date format are empty for remote actors
    op.alter_column(
        'users', 'email', existing_type=sa.VARCHAR(length=255),
        nullable=True
    )
    op.alter_column(
        'users', 'password', existing_type=sa.VARCHAR(length=255),
        nullable=True
    )
    op.alter_column('users', 'date_format', nullable=True)
    # privacy levels
    privacy_levels.create(op.get_bind())
    op.add_column(
        'users',
        sa.Column(
            'workouts_visibility',
            privacy_levels,
            server_default='PRIVATE',
            nullable=True,
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'map_visibility',
            privacy_levels,
            server_default='PRIVATE',
            nullable=True,
        ),
    )
    # create local actors with keys (even if federation is not enabled)
    # and update users
    user_helper = sa.Table(
        'users',
        sa.MetaData(),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=20), nullable=False),
    )
    connection = op.get_bind()
    domain = connection.execute(domain_table.select()).fetchone()
    for user in connection.execute(user_helper.select()):
        op.execute(
            "UPDATE users "
            "SET manually_approves_followers = True, "
            "    is_remote = False, "
            "    workouts_visibility = 'PRIVATE', "
            "    map_visibility = 'PRIVATE' "
            f"WHERE users.id = {user.id}"
        )
        created_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        public_key, private_key = generate_keys()
        op.execute(
            "INSERT INTO actors ("
            "activitypub_id, domain_id, preferred_username, public_key, "
            "private_key, followers_url, following_url, profile_url, "
            "inbox_url, outbox_url, shared_inbox_url, created_at) "
            "VALUES ("
            f"'{get_ap_url(user.username, 'user_url')}', "
            f"{domain.id}, '{user.username}', "
            f"'{public_key}', '{private_key}', "
            f"'{get_ap_url(user.username, 'followers')}', "
            f"'{get_ap_url(user.username, 'following')}', "
            f"'{get_ap_url(user.username, 'profile_url')}', "
            f"'{get_ap_url(user.username, 'inbox')}', "
            f"'{get_ap_url(user.username, 'outbox')}', "
            f"'{get_ap_url(user.username, 'shared_inbox')}', "
            f"'{created_at}'::timestamp) RETURNING id"
        )
        actor = connection.execute(
            actors_table.select().where(
                actors_table.c.preferred_username == user.username
            )
        ).fetchone()
        op.execute(
            f'UPDATE users SET actor_id = {actor.id} WHERE users.id = {user.id}'
        )
    op.alter_column('users', 'manually_approves_followers', nullable=False)
    op.alter_column('users', 'is_remote', nullable=False)
    op.alter_column('users', 'workouts_visibility', nullable=False)
    op.alter_column('users', 'map_visibility', nullable=False)
    op.create_unique_constraint(
        'username_actor_id_unique', 'users', ['username', 'actor_id']
    )

    op.create_table(
        'follow_requests',
        sa.Column('follower_user_id', sa.Integer(), nullable=False),
        sa.Column('followed_user_id', sa.Integer(), nullable=False),
        sa.Column('is_approved', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['followed_user_id'],
            ['users.id'],
        ),
        sa.ForeignKeyConstraint(
            ['follower_user_id'],
            ['users.id'],
        ),
        sa.PrimaryKeyConstraint('follower_user_id', 'followed_user_id'),
    )

    op.add_column(
        'workouts',
        sa.Column(
            'workout_visibility',
            privacy_levels,
            server_default='PRIVATE',
            nullable=True
        )
    )
    op.add_column(
        'workouts',
        sa.Column(
            'map_visibility',
            privacy_levels,
            server_default='PRIVATE',
            nullable=True
        )
    )
    op.add_column(
        'workouts',
        sa.Column('ap_id', sa.Text(), nullable=True)
    )
    op.add_column(
        'workouts',
        sa.Column('remote_url', sa.Text(), nullable=True)
    )
    op.execute(
        "UPDATE workouts "
        "SET workout_visibility = 'PRIVATE', "
        "    map_visibility = 'PRIVATE' "
    )
    op.alter_column('workouts', 'workout_visibility', nullable=False)
    op.alter_column('workouts', 'map_visibility', nullable=False)

    privacy_levels.create(op.get_bind())
    op.create_table('comments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('uuid', UUID(as_uuid=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('workout_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('modification_date', sa.DateTime(), nullable=True),
    sa.Column('text', sa.String(), nullable=False),
    sa.Column('reply_to', sa.Integer(), nullable=True),
    sa.Column('ap_id', sa.Text(), nullable=True),
    sa.Column('remote_url', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workout_id'], ['workouts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['reply_to'], ['comments.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uuid')
    )
    op.add_column(
        'comments',
        sa.Column(
            'text_visibility',
            privacy_levels,
            server_default='PRIVATE',
            nullable=False
        )
    )
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comments_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comments_workout_id'), ['workout_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comments_reply_to'), ['reply_to'], unique=False)

    op.create_table('mentions',
    sa.Column('comment_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('comment_id', 'user_id')
    )

    op.create_table('workout_likes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('workout_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workout_id'], ['workouts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('workout_likes', schema=None) as batch_op:
        batch_op.create_unique_constraint('user_id_workout_id_unique', ['user_id', 'workout_id'])

    op.create_table('comment_likes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('comment_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('comment_likes', schema=None) as batch_op:
        batch_op.create_unique_constraint('user_id_comment_id_unique', ['user_id', 'comment_id'])

def downgrade():

    with op.batch_alter_table('comment_likes', schema=None) as batch_op:
        batch_op.drop_constraint('user_id_comment_id_unique', type_='unique')
    op.drop_table('comment_likes')

    with op.batch_alter_table('workout_likes', schema=None) as batch_op:
        batch_op.drop_constraint('user_id_workout_id_unique', type_='unique')
    op.drop_table('workout_likes')

    op.drop_table('mentions')

    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_comments_user_id'))
        batch_op.drop_index(batch_op.f('ix_comments_workout_id'))
        batch_op.drop_index(batch_op.f('ix_comments_reply_to'))
    op.drop_table('comments')

    op.drop_column('workouts', 'remote_url')
    op.drop_column('workouts', 'ap_id')
    op.drop_column('workouts', 'map_visibility')
    op.drop_column('workouts', 'workout_visibility')

    op.drop_table('follow_requests')

    # remove remote users (for which password is NULL)
    op.execute(
        "DELETE FROM users WHERE password IS NULL;"
    )
    op.drop_constraint('username_actor_id_unique', 'users', type_='unique')
    op.alter_column(
        'users', 'password', existing_type=sa.VARCHAR(length=255),
        nullable=False
    )
    op.alter_column(
        'users', 'email', existing_type=sa.VARCHAR(length=120), nullable=False
    )
    op.drop_constraint('users_actor_id_fkey', 'users', type_='foreignkey')
    op.drop_constraint('users_actor_id_key', 'users', type_='unique')
    op.drop_column('users', 'map_visibility')
    op.drop_column('users', 'workouts_visibility')
    privacy_levels.drop(op.get_bind())
    op.drop_column('users', 'is_remote')
    op.drop_column('users', 'manually_approves_followers')
    op.drop_column('users', 'actor_id')

    op.drop_index(
        op.f('ix_remote_actors_stats_actor_id'),
        table_name='remote_actors_stats'
    )
    op.drop_table('remote_actors_stats')

    op.drop_table('actors')
    op.execute('DROP TYPE actor_types')
    op.create_unique_constraint('users_username_key', 'users', ['username'])

    op.drop_table('domains')