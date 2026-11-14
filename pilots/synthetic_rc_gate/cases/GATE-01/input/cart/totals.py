def summary(items):
    return {"count": len(items), "total": sum(i["price"] for i in items)}
