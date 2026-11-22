"""Run the counter against a real local Redis without Docker or Kubernetes."""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.read().decode("utf-8")


@unittest.skipUnless(shutil.which("redis-server"), "redis-server is required")
class CounterIntegrationTest(unittest.TestCase):
    def test_init_readiness_and_counter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            redis_port, app_port = free_port(), free_port()
            env = os.environ.copy()
            env.update(
                REDIS_HOST="127.0.0.1",
                REDIS_PORT=str(redis_port),
                BOOT_MARKER=str(Path(temp_dir) / "redis-ready"),
                PORT=str(app_port),
            )
            redis = subprocess.Popen(
                [
                    "redis-server", "--bind", "127.0.0.1", "--port", str(redis_port),
                    "--save", "", "--appendonly", "no", "--dir", temp_dir,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            app = subprocess.Popen(
                [sys.executable, "-u", str(APP_DIR / "server.py")],
                cwd=APP_DIR,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                base = f"http://127.0.0.1:{app_port}"
                for _ in range(50):
                    try:
                        if get(base + "/health/live")[0] == 200:
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    self.fail("app did not start")

                self.assertEqual(get(base + "/health/ready")[0], 503)
                subprocess.run(
                    [sys.executable, "-u", str(APP_DIR / "wait_for_redis.py")],
                    cwd=APP_DIR,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertTrue(Path(env["BOOT_MARKER"]).is_file())
                self.assertEqual(get(base + "/health/ready"), (200, "ready\n"))
                self.assertIn("Visits: <strong>1</strong>", get(base + "/")[1])
                self.assertIn("Visits: <strong>2</strong>", get(base + "/")[1])
            finally:
                for process in (app, redis):
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
