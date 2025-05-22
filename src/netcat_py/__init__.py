from __future__ import annotations

import argparse
import queue
import shutil
import socket
import sys
import threading
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from _typeshed import SupportsRead, SupportsWrite


def info(msg: str) -> None:
    print(msg, file=sys.stderr)


def copier(fsrc: SupportsRead[bytes], fdst: SupportsWrite[bytes], exc_q: queue.SimpleQueue[BaseException | None]) -> None:
    try:
        shutil.copyfileobj(fsrc, fdst)
    except BaseException as e:
        exc_q.put(e)
    else:
        exc_q.put(None)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('-v', '--verbose', action='store_true')
    p.add_argument('-l', '--listen', action='store_true')
    p.add_argument('-p', '--local-port', type=int)
    p.add_argument('host', nargs='?')
    p.add_argument('port', type=int, nargs='?')
    args = p.parse_args()

    verb = info if args.verbose else lambda _: None

    s = socket.socket()

    if args.listen:
        if not args.local_port:
            p.error('Must specify local port to listen to')
        if socket.has_dualstack_ipv6():
            srv = socket.create_server(('', args.local_port), family=socket.AF_INET6, dualstack_ipv6=True)
        else:
            srv = socket.create_server(('', args.local_port))
        verb(f'Listening on port {s.getsockname()[1]}')
        sock, client_addr = srv.accept()
        verb(f'Connection from {client_addr[0]}:{client_addr[1]}')
    else:
        if not (args.host and args.port):
            p.error('Must specify host and port to connect to')
        verb(f'Connecting to {args.host}:{args.port}')
        try:
            sock = socket.create_connection((args.host, args.port), source_address=('', args.local_port) if args.local_port else None)
        except Exception as e:
            info(f'Error! {e}')
            raise SystemExit(1) from None

    exc_q = queue.SimpleQueue[BaseException | None]()

    worker_threads = [
        threading.Thread(target=copier, args=(open(0, 'rb', buffering=0), sock.makefile('wb', buffering=0), exc_q), daemon=True),
        threading.Thread(target=copier, args=(sock.makefile('rb', buffering=0), open(1, 'wb', buffering=0), exc_q), daemon=True),
    ]

    for thread in worker_threads:
        thread.start()

    try:
        for _ in worker_threads:
            if (exc := exc_q.get()) is not None:
                raise exc
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    except ConnectionError as e:
        verb(str(e))
    else:
        verb('Done')


if __name__ == '__main__':
    main()
