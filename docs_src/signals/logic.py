async def create_user(**kwargs):
    """
    Creates a user
    """
    await User.query.create(**kwargs)


async def is_verified_user(id: int):
    """
    Checks if user is verified and sends notification
    if true.
    """
    user = await User.query.get(pk=id)

    if user.is_verified:
        # triggers the custom signal
        await User.meta.signals.on_verify.send(sender=User, instance=user)
