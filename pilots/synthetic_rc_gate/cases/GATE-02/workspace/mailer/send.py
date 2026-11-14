from mailer._runtime import quiet_mode

SENT = []


def send(to, body):
    if not to:
        return False
    if not quiet_mode():
        print("sending to", to)
    SENT.append((to, body))
    return True
