SENT = []


def send(to, body):
    SENT.append((to, body))
    return True
