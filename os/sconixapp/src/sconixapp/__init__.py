"""Sconix Systems — shared backend batteries.

Import surface is deliberately small. Every app's ``api/`` installs this
``--editable`` (fix once -> every app gets it), exactly like ``sconixlib`` in
the research OS.

    from sconixapp import Settings, get_settings
    from sconixapp.db import get_session, init_engine
    from sconixapp.security import hash_password, verify_password, create_token, decode_token
    from sconixapp.health import health_router
"""

from sconixapp.config import Settings, get_settings
from sconixapp.logging import configure_logging, get_logger

__all__ = [
    "Settings",
    "get_settings",
    "configure_logging",
    "get_logger",
]
__version__ = "0.1.0"
