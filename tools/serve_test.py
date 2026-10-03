"""Serve the relocated cursor test page on loopback for local development."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from pointer.runtime_paths import WEB_ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9167)
    arguments = parser.parse_args()
    handler = partial(SimpleHTTPRequestHandler, directory=str(WEB_ROOT))
    with ThreadingHTTPServer(("127.0.0.1", arguments.port), handler) as server:
        print(f"Cursor test: http://127.0.0.1:{arguments.port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
