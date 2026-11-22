"""Init-container command: wait for Redis, then publish a shared marker."""

import os
import time

from server import BOOT_MARKER, redis_command


for attempt in range(60):
    try:
        if redis_command("PING") == "PONG":
            with open(BOOT_MARKER, "w", encoding="utf-8") as marker:
                marker.write("Redis was ready before the app started.\n")
            print("Redis is ready; init completed", flush=True)
            break
    except OSError:
        pass
    print(f"Waiting for Redis ({attempt + 1}/60)", flush=True)
    time.sleep(1)
else:
    raise SystemExit("Redis did not become ready within 60 seconds")
