from edgy.core.signals import post_save


def push_notification(email: str) -> None:
    # Sends a push notification
    ...


def send_email(email: str) -> None:
    # Sends an email
    ...


@post_save.connect_via(User)
async def after_creation(sender, instance, **kwargs):
    """
    Sends a notification to the user
    """
    send_email(instance.email)


@post_save.connect_via(User)
async def do_something_else(sender, instance, **kwargs):
    """
    Sends a notification to the user
    """
    push_notification(instance.email)
