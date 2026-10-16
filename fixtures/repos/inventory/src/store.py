"""The inventory: SKU -> quantity, kept in memory."""


class Inventory:
    def __init__(self, items=None):
        self._items = dict(items or {})

    def has(self, sku):
        return sku in self._items

    def quantity(self, sku):
        return self._items.get(sku, 0)

    def set_quantity(self, sku, qty):
        """Set a SKU's quantity. Callers pass validated values; this does not fail for a non-empty SKU and qty >= 0."""
        self._items[sku] = qty

    def adjust(self, sku, delta):
        """Manual stock correction. Going below zero raises ValueError and changes nothing."""
        new = self.quantity(sku) + delta
        if new < 0:
            raise ValueError(f"{sku} would go below zero")
        self._items[sku] = new

    def report(self):
        """One "sku: quantity" line per SKU, ordered by SKU."""
        return [f"{sku}: {qty}" for sku, qty in sorted(self._items.items())]

    def snapshot(self):
        """A copy of the current state, for comparisons."""
        return dict(self._items)
