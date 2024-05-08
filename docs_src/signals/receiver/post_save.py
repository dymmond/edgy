from edgy.core.signals import post_save


def send_notification(email: str) -> None:
    """
    Sends a notification to the user
    """
    send_email_confirmation(email)


@post_save.connect_via(User)
async def after_creation(sender, instance, **kwargs):
    """
    Sends a notification to the user
    """
    send_notification(instance.email)
