"""Vercel Python serverless entrypoint.

The runtime imports this module and looks for a module-level WSGI callable named
`app`. The repo root is added to sys.path because the function's working
directory is not guaranteed to be the project root at import time.

Routing: vercel.json rewrites /api/(.*) here, and Vercel rewrites preserve the
original request path, so Flask sees /api/analyze rather than /api/index.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.app import create_app  # noqa: E402

app = create_app()
