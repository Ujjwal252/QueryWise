
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect


# Shared rate limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
    strategy="fixed-window"
)


# Shared CSRF protection instance
csrf = CSRFProtect()
