def describe(item):
    return {"sku": item["sku"], "qty": item["qty"], "low": item["qty"] < 5}
