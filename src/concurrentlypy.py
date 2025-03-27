"""A minimum Python port of Node.js's `concurrently` tool."""

import asyncio
import os
import signal
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from contextlib import suppress


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
    parser.add_argument(
        "--hard-kill-wait",
        type=float,
        default=5.0,
        help=(
            "Time in seconds to wait for a graceful shutdown before hard kill. "
            "Set to 0 to disable forced kill."
        ),
    )
    return parser.parse_args()


async def run_command(
    command: str,
    hard_kill_wait: float,
    stop_event: asyncio.Event,
) -> int | None:
    """Run a single command. Return its exit code."""
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
        pre_exec_fn = None
    else:
        creation_flags = 0
        pre_exec_fn = os.setsid

    proc = await asyncio.create_subprocess_shell(
        command,
        preexec_fn=pre_exec_fn,
        creationflags=creation_flags,
    )

    interrupted = False
    try:
        while True:
            if stop_event.is_set():
                interrupted = True
                break
            with suppress(TimeoutError):
                return await asyncio.wait_for(proc.wait(), timeout=0.1)
    finally:
        if interrupted or stop_event.is_set():
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)

            if hard_kill_wait > 0:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=hard_kill_wait)
                except TimeoutError:
                    proc.kill()

    return None


async def a_main() -> None:
    args = parse_args()
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        if sys.platform == "win32":
            signal.signal(sig, lambda _, __: stop_event.set())
        else:
            loop.add_signal_handler(sig, stop_event.set)

    tasks: list[asyncio.Task[int | None]] = []

    async with asyncio.TaskGroup() as tg:
        for command in args.commands:
            tasks.append(
                tg.create_task(run_command(command, args.hard_kill_wait, stop_event))
            )

        while not stop_event.is_set():
            for task in tasks:
                if not task.done():
                    continue
                ret = task.result()
                if args.kill_others or (
                    args.kill_others_on_fail and ret not in (0, None)
                ):
                    stop_event.set()
                    for t in tasks:
                        t.cancel()
                    break
            if all(task.done() for task in tasks):
                break
            await asyncio.sleep(0.1)

    for task in tasks:
        if task.cancelled():
            continue
        ret = task.result()
        if ret not in (0, None):
            sys.exit(ret)


def main() -> None:
    asyncio.run(a_main())


if __name__ == "__main__":
    main()
