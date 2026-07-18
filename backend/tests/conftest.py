"""
Pytest bootstrap. Runs before any test module imports `app.config`.

Config defaults are fail-closed (an unset APP_ENV means production, which would
reject the weak default SECRET_KEY at import). The test suite is not production,
so declare that explicitly here — the same way local dev opts out via .env.
"""
import os

os.environ.setdefault("APP_ENV", "testing")
