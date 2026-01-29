#!/usr/bin/env python3
"""Entry point for Mini ATS."""
from mini_ats.app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=port)
