import random


class ProxyRotator:
    """Simple in-memory proxy rotation abstraction for managed network routing."""

    def __init__(self, proxies=None):
        self.proxies = proxies or [
            {"ip": f"103.75.190.{i}", "port": 8080, "country": "Pakistan"}
            for i in range(1, 4)
        ]

    def next(self):
        return random.choice(self.proxies)

    def get_best_proxy(self, phone_number=None):
        """Return the best available proxy for the given target."""
        return random.choice(self.proxies)

    def shutdown(self):
        return True
