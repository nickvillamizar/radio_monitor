#!/usr/bin/env python
"""Simple test server without monitor thread"""
import sys
sys.path.insert(0, '.')

from app import app, db

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    # Start without monitor thread
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )
