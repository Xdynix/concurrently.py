"""A minimum Python port of Node.js's `concurrently` tool."""

import shlex
import signal
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from threading import Event


def parse_args() -> Namespace:
    parser = ArgumentParser(description="Run multiple commands concurrently.")
    parser.add_argument(
        "commands",
        nargs="+",
        metavar="COMMAND",
        help="Commands to run.",
    )
    parser.add_argument(
        "-k",
        "--kill-others",
        action="store_true",
        help="Kill other processes if one exits or dies.",
    )
    parser.add_argument(
        "--kill-others-on-fail",
        action="store_true",
        help="Kill other processes if one exits with non zero status code.",
    )
    return parser.parse_args()


def run_command(command: str, stop_event: Event) -> int | None:
    """Run a single command. Return its exit code. Or `None` if terminated."""
    with subprocess.Popen(shlex.split(command)) as proc:  # noqa: S603
        while not stop_event.wait(0.1) and proc.poll() is None:
            pass
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_C_EVENT)
        else:
            proc.terminate()
    return proc.poll()


def main() -> None:
    args = parse_args()

    stop_event = Event()

    def done_callback(f: Future[int | None]) -> None:
        result = f.result()
        if args.kill_others or args.kill_others_on_fail and result not in (0, None):
            stop_event.set()

    futures: list[Future[int | None]] = []
    try:
        commands: list[str] = args.commands
        with ThreadPoolExecutor(max_workers=len(commands)) as executor:
            for command in commands:
                future = executor.submit(run_command, command, stop_event)
                futures.append(future)
                future.add_done_callback(done_callback)
    except KeyboardInterrupt:
        stop_event.set()

    for future in as_completed(futures):
        if future.result() not in (0, None):
            sys.exit(future.result())


if __name__ == "__main__":
    main()
