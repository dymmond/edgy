async def trigger_notifications(sender, instance, **kwargs):
    """
    Sends email and push notification
    """
    send_email(instance.email)
    send_push_notification(instance.email)


# Disconnect the given function
User.meta.signals.on_verify.disconnect(trigger_notifications)
