def render_id(n):
    return "#%d" % n


def invoice_title(n):
    return "Invoice " + render_id(n)


def receipt_title(n):
    return "Receipt " + render_id(n)


def label_text(n):
    return "Parcel " + render_id(n)


def email_subject(n):
    return "Your order " + render_id(n)


def audit_line(n):
    return "audit:" + render_id(n)
