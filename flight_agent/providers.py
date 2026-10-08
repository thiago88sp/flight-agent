"""Price providers. Each one exposes ONE of these search styles:

- search(origin, dest, depart, ret) -> offers for one exact pair of dates (grid search);
- search_month(origin, dest, month, round_trip) -> every offer in the month, each with its own
  "depart"/"return" (ISO); search.py filters the date window and trip length locally.

Offer = {"airline": str, "price": float, "stops": int, "currency": str}
"""
import hashlib
import os
import sys
import time


class MockProvider:
    """Deterministic, FAKE prices, only to exercise the flow without credentials."""

    name = "simulated"

    def pop_errors(self):
        return []

    def search(self, origin, dest, depart, ret):
        offers = []
        for airline, base in (("LATAM", 1.0), ("TAP", 0.93), ("Azul", 1.08)):
            seed = f"{origin}{dest}{depart}{ret}{airline}".encode()
            h = int(hashlib.md5(seed).hexdigest(), 16)
            dest_factor = 0.7 + (int(hashlib.md5(dest.encode()).hexdigest(), 16) % 90) / 100
            price = 2200 * base * dest_factor * (0.8 + (h % 700) / 1000)
            if depart.weekday() in (1, 2):  # Tue/Wed tend to be cheaper
                price *= 0.9
            offers.append({"airline": airline, "price": round(price, 2),
                           "stops": h % 3, "currency": "BRL"})
        return offers


class TravelpayoutsProvider:
    """Real (free) prices from the Aviasales Data API via Travelpayouts: travelpayouts.com.

    Prices come from a cache of recent searches made by Aviasales users, not a live query:
    rarely searched routes/dates may come back empty and a price may be a few days old.
    """

    name = "Travelpayouts"
    URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    PAUSE = 0.1  # stay under the requests-per-second limit

    HINTS = {401: "invalid token? check TRAVELPAYOUTS_TOKEN in .env",
             429: "rate limit reached; lower MAX_CALLS or try again later"}

    def __init__(self):
        import requests
        self.requests = requests
        self.headers = {"X-Access-Token": os.environ["TRAVELPAYOUTS_TOKEN"]}
        self.errors = []  # distinct messages since the last pop_errors()

    def _error(self, msg):
        if msg not in self.errors:
            self.errors.append(msg)
            print(f"[error] {msg}", file=sys.stderr)

    def pop_errors(self):
        errs, self.errors = self.errors, []
        return errs

    def search_month(self, origin, dest, month, round_trip):
        """One query per month: the cache rarely holds the exact pair of dates requested, so we
        fetch everything and let search.py filter. Without return_at the return can be on any
        date (even the next month). month=None returns any departure date."""
        params = {"origin": origin, "destination": dest,
                  "currency": "brl", "sorting": "price", "limit": 100,
                  "one_way": "false" if round_trip else "true"}
        if month:
            params["departure_at"] = month
        time.sleep(self.PAUSE)
        try:
            resp = self.requests.get(self.URL, headers=self.headers, params=params, timeout=30)
        except self.requests.RequestException as e:
            self._error(f"Travelpayouts unreachable: {type(e).__name__}")
            return []
        if resp.status_code != 200:
            hint = self.HINTS.get(resp.status_code) or resp.text[:120].strip()
            self._error(f"Travelpayouts HTTP {resp.status_code}: {hint}")
            return []
        body = resp.json()
        currency = body.get("currency", "brl").upper()
        out = []
        for o in body.get("data", []):
            ret = o.get("return_at") if round_trip else None
            out.append({"airline": o.get("airline", "?"),
                        "price": float(o["price"]),
                        "stops": max(o.get("transfers", 0), o.get("return_transfers", 0)),
                        "currency": currency,
                        "depart": o["departure_at"][:10],
                        "return": ret[:10] if ret else None,
                        "link": o.get("link")})  # path on aviasales.com where the ticket can be bought
        return out


def using_mock() -> bool:
    return not os.getenv("TRAVELPAYOUTS_TOKEN")


def get_provider():
    if using_mock():
        print("[warning] no TRAVELPAYOUTS_TOKEN -> using SIMULATED prices", file=sys.stderr)
        return MockProvider()
    return TravelpayoutsProvider()
