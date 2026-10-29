# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Profiling a run for the --debug-log file.

A run given --debug-log is profiled from start to finish. The file gets:

- a "run start" line saying what ran, and a "run end" line with its exit
  status, time, CPU, memory, and how long it waited on the network;
- one "span" line per phase of the run, such as connecting or the command;
- an HTTP "send" line before every request and a "recv" or "fail" line
  after, with the method, URL, headers, sizes, status, and the wait, every
  secret redacted;
- a "resources" line every few seconds: CPU and memory in use;
- at the end, cProfile's table of function run times.

Lines are key=value pairs after the logger name, so they can be filtered
with grep or awk as easily as read. Nothing here runs without --debug-log.
"""

import contextlib
import cProfile
import ctypes
import io
import itertools
import json
import logging
import os
import platform
import pstats
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import plexapi
import requests

from plexdo import __version__
from plexdo.security import hide_request_secrets, redact, redact_headers

PROFILE_LOG = logging.getLogger("plexdo.profile")
HTTP_LOG = logging.getLogger("plexdo.http")

# How often the resources line is written during a run.
SAMPLE_SECONDS = 5.0
# How many functions each cProfile table lists.
TOP_FUNCTIONS = 40

# requests' own send, which _timed_send wraps while a Run is active.
_ORIGINAL_SEND = requests.Session.send


@dataclass(frozen=True)
class Usage:
    """The process's clocks and memory at one moment.

    Memory a platform cannot report is None: current resident memory is
    known on Linux and Windows, and the peak everywhere but where neither
    resource nor the Windows API is present.
    """

    wall_ns: int
    cpu_ns: int
    user_ns: int
    system_ns: int
    rss_bytes: int | None
    peak_rss_bytes: int | None


class _MemoryCounters(ctypes.Structure):
    """PROCESS_MEMORY_COUNTERS, from the Windows process status API."""

    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _windows_memory() -> tuple[int | None, int | None]:
    """The working set and its peak, in bytes, from the Windows API."""
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        psapi = ctypes.windll.psapi  # type: ignore[attr-defined]
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        counters = _MemoryCounters(cb=ctypes.sizeof(_MemoryCounters))
        process = ctypes.c_void_p(kernel32.GetCurrentProcess())
        if not psapi.GetProcessMemoryInfo(
            process, ctypes.byref(counters), counters.cb
        ):
            return None, None
        return counters.WorkingSetSize, counters.PeakWorkingSetSize
    except (AttributeError, OSError):
        return None, None


def _rss_bytes() -> int | None:
    """The resident memory in use now, where the platform says."""
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/self/statm", encoding="ascii") as statm:
                pages = int(statm.read().split()[1])
            return pages * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, IndexError):
            return None
    if os.name == "nt":
        return _windows_memory()[0]
    return None


def _peak_rss_bytes() -> int | None:
    """The most resident memory used so far, where the platform says."""
    if os.name == "nt":
        return _windows_memory()[1]
    try:
        import resource  # pylint: disable=import-outside-toplevel
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Kilobytes, except on macOS, which counts in bytes.
    return peak if sys.platform == "darwin" else peak * 1024


def usage() -> Usage:
    """The process's clocks and memory now."""
    times = os.times()
    rss, peak = _rss_bytes(), _peak_rss_bytes()
    # Linux updates the peak lazily, so it can trail what is in use now.
    if rss is not None and peak is not None:
        peak = max(peak, rss)
    return Usage(
        wall_ns=time.perf_counter_ns(),
        cpu_ns=time.process_time_ns(),
        user_ns=int(times.user * 1e9),
        system_ns=int(times.system * 1e9),
        rss_bytes=rss,
        peak_rss_bytes=peak,
    )


def _between(before: Usage, after: Usage) -> str:
    """The time, CPU, and memory from one Usage to the next, as key=value.

    cpu_percent is CPU time over wall time, so a run waiting on the network
    shows near 0, and one busy in more than one thread can exceed 100.
    """
    wall = after.wall_ns - before.wall_ns
    cpu = after.cpu_ns - before.cpu_ns
    percent = 100 * cpu / wall if wall else 0.0
    return (
        f"wall_ns={wall} cpu_ns={cpu} "
        f"user_ns={after.user_ns - before.user_ns} "
        f"system_ns={after.system_ns - before.system_ns} "
        f"cpu_percent={percent:.1f} rss_bytes={after.rss_bytes} "
        f"peak_rss_bytes={after.peak_rss_bytes}"
    )


def _exit_status(exc: BaseException | None) -> str:
    """How the run ended, for the run end line."""
    if exc is None:
        return "0"
    if isinstance(exc, SystemExit):
        if exc.code is None or isinstance(exc.code, int):
            return str(exc.code or 0)
        return "1"
    if isinstance(exc, KeyboardInterrupt):
        return "interrupted"
    return f"exception:{type(exc).__name__}"


def _body_size(body: Any) -> int | str:
    """The size of a request body, without reading a stream."""
    if body is None:
        return 0
    if isinstance(body, (bytes, str)):
        return len(body)
    return "stream"


class _Totals:
    """The requests a run has made, counted across threads."""

    def __init__(self) -> None:
        self.calls = 0
        self.wait_ns = 0
        self.slowest_ns = 0
        self.slowest = ""
        self.ids = itertools.count(1)
        self.lock = threading.Lock()

    def record(self, waited_ns: int, method: str, url: str) -> None:
        """Add one top-level request."""
        with self.lock:
            self.calls += 1
            self.wait_ns += waited_ns
            if waited_ns > self.slowest_ns:
                self.slowest_ns = waited_ns
                self.slowest = f"{method} {redact(url)}"


class Run:
    """The profile of one run, active while the run is in progress.

    Entering it writes the run start line, starts cProfile, the resource
    sampler, and the HTTP timing; leaving it, however the run ends, stops
    them and writes the totals and the function table.
    """

    current: "Run | None" = None

    def __init__(self, command: str | None) -> None:
        self.command = command
        self.started = usage()
        self.totals = _Totals()
        self.depth = threading.local()
        self.stopping = threading.Event()
        self.sampler = threading.Thread(
            target=self._sample, name="plexdo-sampler", daemon=True
        )
        self.profiler: cProfile.Profile | None = cProfile.Profile()

    def __enter__(self) -> "Run":
        """Write the run start line and start profiling."""
        PROFILE_LOG.debug(
            "run start plexdo=%s python=%s plexapi=%s requests=%s "
            "platform=%s pid=%d command=%s argv=%s",
            __version__,
            platform.python_version(),
            plexapi.VERSION,
            requests.__version__,
            platform.platform(),
            os.getpid(),
            self.command,
            json.dumps(sys.argv),
        )
        Run.current = self
        requests.Session.send = _timed_send  # type: ignore[method-assign]
        self.sampler.start()
        try:
            self.profiler.enable()  # type: ignore[union-attr]
        except ValueError as exc:
            # Python 3.12 and later allow one profiler at a time; a
            # debugger or coverage tool may hold it already.
            PROFILE_LOG.debug("function profiling unavailable: %s", exc)
            self.profiler = None
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """Stop profiling and write the totals, however the run ended."""
        if self.profiler:
            self.profiler.disable()
        self.stopping.set()
        self.sampler.join()
        requests.Session.send = _ORIGINAL_SEND  # type: ignore[method-assign]
        Run.current = None
        if exc is not None and not isinstance(
            exc, (SystemExit, KeyboardInterrupt)
        ):
            PROFILE_LOG.debug("run failed", exc_info=exc)
        ended = usage()
        wall = ended.wall_ns - self.started.wall_ns
        totals = self.totals
        PROFILE_LOG.debug(
            "run end status=%s %s api_calls=%d api_wait_ns=%d "
            "api_wait_percent=%.1f slowest_api_ns=%d slowest_api=%s",
            _exit_status(exc),
            _between(self.started, ended),
            totals.calls,
            totals.wait_ns,
            100 * totals.wait_ns / wall if wall else 0.0,
            totals.slowest_ns,
            totals.slowest or "none",
        )
        self._write_functions()

    def _sample(self) -> None:
        """Write a resources line every SAMPLE_SECONDS until stopped."""
        last = self.started
        while not self.stopping.wait(SAMPLE_SECONDS):
            now = usage()
            PROFILE_LOG.debug(
                "resources since_previous %s", _between(last, now)
            )
            last = now

    def _write_functions(self) -> None:
        """Write cProfile's tables: by time including callees, and own."""
        if not self.profiler:
            return
        for order, title in (
            ("cumulative", "cumulative time, callees included"),
            ("tottime", "own time, callees excluded"),
        ):
            table = io.StringIO()
            stats = pstats.Stats(self.profiler, stream=table)
            stats.sort_stats(order).print_stats(TOP_FUNCTIONS)
            PROFILE_LOG.debug(
                "functions by %s (cProfile, top %d):\n%s",
                title,
                TOP_FUNCTIONS,
                table.getvalue().strip("\n"),
            )


def _timed_send(
    session: requests.Session, request: requests.PreparedRequest, **kwargs
) -> requests.Response:
    """requests.Session.send, logged and timed for the active Run.

    Every session plexdo, plexapi, or anything else opens goes through
    here. A redirect comes back through as a request of its own; only the
    outermost counts toward the totals, so its wait is not counted twice.
    """
    run = Run.current
    if run is None:
        return _ORIGINAL_SEND(session, request, **kwargs)
    method, url = request.method or "?", request.url or ""
    hide_request_secrets(url, request.headers)
    call = next(run.totals.ids)
    depth = getattr(run.depth, "value", 0)
    HTTP_LOG.debug(
        "send id=%d method=%s url=%s bytes=%s headers=%s",
        call,
        method,
        redact(url),
        _body_size(request.body),
        json.dumps(redact_headers(request.headers)),
    )
    run.depth.value = depth + 1
    started = time.perf_counter_ns()
    try:
        response = _ORIGINAL_SEND(session, request, **kwargs)
    except Exception as exc:
        waited = time.perf_counter_ns() - started
        if depth == 0:
            run.totals.record(waited, method, url)
        HTTP_LOG.debug(
            "fail id=%d wait_ns=%d error=%s: %s",
            call,
            waited,
            type(exc).__name__,
            exc,
        )
        raise
    finally:
        run.depth.value = depth
    waited = time.perf_counter_ns() - started
    if depth == 0:
        run.totals.record(waited, method, url)
    size: int | str
    if kwargs.get("stream"):
        size = response.headers.get("Content-Length", "streamed")
    else:
        size = len(response.content)
    HTTP_LOG.debug(
        "recv id=%d status=%d reason=%s wait_ns=%d headers_ns=%d "
        "bytes=%s type=%s headers=%s",
        call,
        response.status_code,
        json.dumps(response.reason),
        waited,
        int(response.elapsed.total_seconds() * 1e9),
        size,
        response.headers.get("Content-Type", "none"),
        json.dumps(redact_headers(response.headers)),
    )
    return response


@contextlib.contextmanager
def span(name: str) -> Iterator[None]:
    """Time one phase of the run for the debug log; nothing without one.

    The span line gives the phase's time, CPU, and memory, and how many
    requests it made and how long they took.
    """
    run = Run.current
    if run is None:
        yield
        return
    totals = run.totals
    before, calls, waited = usage(), totals.calls, totals.wait_ns
    try:
        yield
    finally:
        PROFILE_LOG.debug(
            "span name=%s %s api_calls=%d api_wait_ns=%d",
            name,
            _between(before, usage()),
            totals.calls - calls,
            totals.wait_ns - waited,
        )


def profiled(enabled: bool, command: str | None):
    """The context to run a command in: a Run, or nothing at all."""
    return Run(command) if enabled else contextlib.nullcontext()
