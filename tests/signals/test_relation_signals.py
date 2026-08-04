from functools import partial

import pytest

import edgy
from edgy.core.signals import (
    Signal,
    post_delete,
    post_relation_add,
    post_relation_remove,
    pre_delete,
    pre_relation_add,
    pre_relation_remove,
)
from edgy.exceptions import RelationshipNotFound
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(
    DATABASE_URL, drop_database=True, force_rollback=False, full_isolation=False
)
models = edgy.Registry(database=database)


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    profile = edgy.ForeignKey("Profile", null=True, on_delete=edgy.CASCADE, related_name="users")
    friends = edgy.ManyToMany("Friend", related_name="users")

    class Meta:
        registry = models


class Friend(edgy.StrictModel):
    name: str = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Profile(edgy.StrictModel):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Log(edgy.StrictModel):
    signal = edgy.CharField(max_length=255)
    class_name = edgy.CharField(max_length=255)
    params = edgy.JSONField()

    class Meta:
        registry = models

    def __str__(self) -> str:
        return str(self.extract_db_fields())

    def __repr__(self) -> str:
        return f"Log<{self}>"


@pytest.fixture(autouse=True, scope="function")
async def create_test_database():
    async with models:
        await models.create_all()
        yield


async def pre_add(sender, **kwargs):
    await Log.query.create(
        signal="pre_relation_add",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


async def pre_add_injected(sender, **kwargs):
    kwargs.setdefault("injected", True)
    await Log.query.create(
        signal="pre_relation_add",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


async def post_add(sender, **kwargs):
    await Log.query.create(
        signal="post_relation_add",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


async def pre_remove(sender, **kwargs):
    await Log.query.create(
        signal="pre_relation_remove",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


async def post_remove(sender, **kwargs):
    await Log.query.create(
        signal="post_relation_remove",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


async def pre_delete_fn(sender, **kwargs):
    await Log.query.create(
        signal="pre_delete",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


async def post_delete_fn(sender, **kwargs):
    await Log.query.create(
        signal="post_delete",
        class_name=sender.__name__,
        params={k: str(v) for k, v in kwargs.items()},
    )


class SpecialException(Exception):
    pass


async def abort_removal(sender, raw_values, **kwargs):
    raise SpecialException()


async def nullify_removal(sender, raw_values, update_params=None, **kwargs):
    raw_values.clear()


@pytest.fixture(autouse=True, scope="function")
async def connect_signals():
    through = User.meta.fields["friends"].through
    for signal_class in [through, User, Friend, Profile]:
        pre_relation_add.connect(pre_add, signal_class, weak=True)
        post_relation_add.connect(post_add, signal_class, weak=True)
        pre_relation_remove.connect(pre_remove, signal_class, weak=True)
        post_relation_remove.connect(post_remove, signal_class, weak=True)
        pre_delete.connect(pre_delete_fn, signal_class, weak=True)
        post_delete.connect(post_delete_fn, signal_class, weak=True)

    try:
        yield
    finally:
        pre_relation_add.disconnect(pre_add)
        post_relation_add.disconnect(post_add)
        pre_relation_remove.disconnect(pre_remove)
        post_relation_remove.disconnect(post_remove)
        pre_delete.disconnect(pre_delete_fn)
        post_delete.disconnect(post_delete_fn)


@pytest.mark.parametrize("klass", [User.meta.fields["friends"].through, Profile])
async def test_correct_connection(klass):
    assert pre_relation_add.has_receivers_for(klass)
    assert post_relation_add.has_receivers_for(klass)
    assert pre_relation_remove.has_receivers_for(klass)
    assert post_relation_remove.has_receivers_for(klass)


async def test_basic_m2m():
    user = await User.query.create(name="Edgy")
    assert await Log.query.count() == 0
    await user.friends.add(Friend(name="saffier"))
    friends = await user.friends.all()
    assert len(friends) == 1
    logs = await Log.query.all()
    assert len(logs) == 2
    assert logs[0].signal == "pre_relation_add"
    # see docs for parameters
    assert len(logs[0].params) == 9
    assert logs[1].signal == "post_relation_add"
    assert len(logs[1].params) == 12
    assert logs[0].params["raw_values"]
    assert "User" in logs[0].params["source"]
    assert "Friend" in logs[0].params["target"]
    assert logs[0].params["instance"] == str(user)
    assert logs[0].class_name == "UserFriendsThrough"
    assert logs[0].params["operation"] == "add"
    assert logs[0].params["field"] == "friends"
    assert logs[0].params["relation"] == "many_to_many"
    assert logs[0].params["create_params"]
    assert logs[0].params["update_params"]
    assert "values" not in logs[0].params
    assert "row_count" not in logs[0].params
    assert "row_count_create" not in logs[0].params
    assert logs[1].params["instance"] == str(user)
    assert logs[1].signal == "post_relation_add"
    assert logs[1].params["values"]
    assert logs[1].params["row_count"] == "1"
    assert logs[1].params["row_count_create"] == "1"
    # nothing happens
    with pytest.raises(RelationshipNotFound):
        await user.friends.remove()
    assert await Log.query.count() == 2
    await user.friends.remove_many(*friends)
    logs = await Log.query.all()
    assert len(logs) == 4
    assert logs[2].signal == "pre_relation_remove"
    assert len(logs[2].params) == 7
    assert logs[2].params["instance"] == str(user)
    assert "operation" not in logs[2].params
    assert "values" not in logs[2].params
    assert "create_params" not in logs[2].params
    assert "update_params" not in logs[2].params
    assert logs[3].signal == "post_relation_remove"
    # see docs for parameters
    assert len(logs[3].params) == 8
    assert logs[3].params["instance"] == str(user)
    assert "operation" not in logs[3].params
    assert "values" not in logs[3].params
    assert "model_based_deletion" in logs[3].params
    assert "create_params" not in logs[3].params
    assert "update_params" not in logs[3].params
    assert logs[3].params["row_count"] == "1"
    assert await Log.query.filter(signal="post_delete").count() == 0
    assert await Log.query.filter(signal="pre_delete").count() == 0


async def test_basic_one_to_many():
    profile = await Profile.query.create(name="Edgy")
    assert await Log.query.count() == 0
    await profile.users.create(name="saffier", friends=[Friend(name="ravyn")])
    users = await profile.users.all()
    assert len(users) == 1
    logs = await Log.query.all()
    assert len(logs) == 4
    assert logs[0].signal == "pre_relation_add"
    # nested fk
    assert logs[1].signal == "pre_relation_add"
    assert logs[2].signal == "post_relation_add"
    assert logs[3].signal == "post_relation_add"
    assert logs[0].params["raw_values"]
    assert logs[0].params["instance"] == str(profile)
    assert "Profile" in logs[0].params["source"]
    assert "User" in logs[0].params["target"]
    assert logs[0].class_name == "User"
    assert logs[0].params["operation"] == "add"
    assert logs[0].params["field"] == "users"
    assert logs[0].params["relation"] == "one_to_many"
    assert logs[0].params["create_params"]
    assert logs[0].params["update_params"]
    await profile.users.remove(users[0])
    logs = await Log.query.all()
    assert len(logs) == 6
    assert logs[4].signal == "pre_relation_remove"
    # see docs for parameters
    assert len(logs[4].params) == 6
    assert "operation" not in logs[4].params
    assert "values" not in logs[4].params
    assert "create_params" not in logs[4].params
    assert "update_params" not in logs[4].params
    assert logs[4].params["instance"] == str(profile)
    assert "model_based_deletion" not in logs[4].params
    assert logs[5].signal == "post_relation_remove"
    # see docs for parameters
    assert len(logs[5].params) == 7
    assert "operation" not in logs[5].params
    assert "values" not in logs[5].params
    assert "create_params" not in logs[5].params
    assert "update_params" not in logs[5].params
    assert logs[5].params["row_count"] == "1"
    assert logs[5].params["instance"] == str(profile)
    assert await Log.query.filter(signal="post_delete").count() == 0
    assert await Log.query.filter(signal="pre_delete").count() == 0


async def test_abort_many_to_many():
    through = User.meta.fields["friends"].through
    user = await User.query.create(name="Edgy")
    await user.friends.add(Friend(name="saffier"))

    User.meta.signals.pre_relation_remove = Signal()
    assert not User.meta.signals.pre_relation_remove.has_receivers_for(through)
    User.meta.signals.pre_relation_remove.connect(abort_removal, through)
    try:
        assert User.meta.signals.pre_relation_remove.has_receivers_for(through)
        with pytest.raises(SpecialException):
            await user.friends.remove_many(*(await user.friends.all()))
        assert len(await user.friends.all()) == 1
        # delete all
        await user.friends.delete()
        assert len(await user.friends.all()) == 0
        await user.friends.remove_many(*(await user.friends.all()))

    finally:
        User.meta.signals.pre_relation_remove.disconnect(abort_removal)
        User.meta.signals.pre_relation_remove = pre_relation_remove

    assert await Log.query.filter(signal="pre_delete").count() == 1
    assert await Log.query.filter(signal="post_delete").count() == 1


async def test_abort_one_to_many():
    profile = await Profile.query.create(name="Edgy")
    await profile.users.create(name="saffier")

    Profile.meta.signals.pre_relation_remove = Signal()
    assert not Profile.meta.signals.pre_relation_remove.has_receivers_for(User)
    Profile.meta.signals.pre_relation_remove.connect(abort_removal, User)
    try:
        assert Profile.meta.signals.pre_relation_remove.has_receivers_for(User)
        with pytest.raises(SpecialException):
            await profile.users.remove_many(*(await profile.users.all()))
        assert len(await profile.users.all()) == 1
        # delete all
        await profile.users.delete()
        await profile.users.remove_many(*(await profile.users.all()))

    finally:
        Profile.meta.signals.pre_relation_remove.disconnect(abort_removal)
        Profile.meta.signals.pre_relation_remove = pre_relation_remove

    assert await Log.query.filter(signal="pre_delete").count() == 1
    assert await Log.query.filter(signal="post_delete").count() == 1


async def test_nullify_many_to_many():
    through = User.meta.fields["friends"].through
    user = await User.query.create(name="Edgy")
    await user.friends.add_many(Friend(name="saffier"), {"name": "saffier2"})
    assert len(await user.friends.all()) == 2

    Friend.meta.signals.pre_relation_remove.connect(nullify_removal, through)
    # shared
    assert User.meta.signals.pre_relation_remove.has_receivers_for(through)
    try:
        await user.friends.remove_many(*(await user.friends.all()))
    finally:
        Friend.meta.signals.pre_relation_remove.disconnect(nullify_removal)
    assert len(await user.friends.all()) == 2


async def test_nullify_one_to_many():
    profile = await Profile.query.create(name="Edgy")
    await profile.users.create(name="saffier")
    await profile.users.create(name="saffier2")
    assert len(await profile.users.all()) == 2

    Profile.meta.signals.pre_relation_remove.connect(nullify_removal, User)
    try:
        await profile.users.remove_many(*(await profile.users.all()))

    finally:
        User.meta.signals.pre_relation_remove.disconnect(nullify_removal)

    assert len(await profile.users.all()) == 2


@pytest.mark.parametrize(
    "signal_class", [User, Friend, Profile, User.meta.fields["friends"].through]
)
async def test_overwrite(signal_class, subtests):
    through = User.meta.fields["friends"].through
    signal_class.meta.signals.pre_relation_add = Signal()
    signal_class.meta.signals.post_relation_add = Signal()
    signal_class.meta.signals.pre_relation_remove = Signal()
    signal_class.meta.signals.post_relation_remove = Signal()
    for signal_class2 in [through, User, Friend, Profile]:
        assert not signal_class.meta.signals.pre_relation_add.has_receivers_for(signal_class2)
        pre_add_fn = signal_class.meta.signals.pre_relation_add.connect(
            pre_add_injected, signal_class2, weak=True
        )
        assert signal_class.meta.signals.pre_relation_add.has_receivers_for(signal_class2)
        post_add_fn = signal_class.meta.signals.post_relation_add.connect(
            partial(post_add, injected=True), signal_class2, weak=False
        )
        pre_remove_fn = signal_class.meta.signals.pre_relation_remove.connect(
            partial(pre_remove, injected=True), signal_class2, weak=False
        )
        post_remove_fn = signal_class.meta.signals.post_relation_remove.connect(
            partial(post_remove, injected=True), signal_class2, weak=False
        )
    try:
        profile = await Profile.query.create(name="Edgy")
        assert await Log.query.count() == 0
        await profile.users.create(name="saffier", friends=[Friend(name="ravyn")])
        friend = await Friend.query.get()
        with (
            signal_class.meta.signals.pre_relation_add.muted(),
            signal_class.meta.signals.post_relation_add.muted(),
            pre_relation_add.muted(),
            post_relation_add.muted(),
        ):
            await friend.users.create(name="monkay")
        await profile.users.remove_many(*(await profile.users.all()))
        await friend.users.remove_many(*(await friend.users.all()))
    finally:
        signal_class.meta.signals.pre_relation_add.disconnect(pre_add_fn)
        signal_class.meta.signals.pre_relation_add = pre_relation_add
        signal_class.meta.signals.post_relation_add.disconnect(post_add_fn)
        signal_class.meta.signals.post_relation_add = post_relation_add

        signal_class.meta.signals.pre_relation_remove.disconnect(pre_remove_fn)
        signal_class.meta.signals.pre_relation_remove = pre_relation_remove
        signal_class.meta.signals.post_relation_remove.disconnect(post_remove_fn)
        signal_class.meta.signals.post_relation_remove = post_relation_remove

    logs = await Log.query.all()
    for signal_name in [
        "pre_relation_add",
        "post_relation_add",
        "pre_relation_remove",
        "post_relation_remove",
    ]:
        with subtests.test(msg=f"test signal: {signal_name}"):
            count_injected = 0
            count_normal = 0
            for log in logs:
                if log.signal != signal_name:
                    continue
                if "injected" in log.params:
                    count_injected += 1
                else:
                    count_normal += 1

            assert count_injected == (2 if signal_class is User else 1)
            assert count_normal > 0
