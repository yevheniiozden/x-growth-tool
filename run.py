#!/usr/bin/env python3
"""Simple script to run the X Growth AI Tool"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )

