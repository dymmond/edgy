from edgy.core.signals import post_save


def send_notification(email: str) -> None:
    """
    Sends a notification to the user
    """
    send_email_confirmation(email)


@post_save(User)
async def after_creation(sender, instance, **kwargs):
    """
    Sends a notification to the user
    """
    send_notification(instance.email)


# Disconnect the given function
User.meta.signals.post_save.disconnect(after_creation)

# Signals are also exposed via instance
user.signals.post_save.disconnect(after_creation)
