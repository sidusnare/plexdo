# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""The --debug-log file: timestamps, redaction, and profiling."""

import base64
import logging
import os
import re

import pytest
import requests
from requests.adapters import BaseAdapter

from plexdo import profiling, secret_store
from plexdo.logs import TimestampedFormatter, configure_logging
from plexdo.security import hide_in_logs, hide_request_secrets, redact

STAMPED = re.compile(r"^\d{19} ")


@pytest.fixture
def root_handlers():
    """Restore the root logger after configure_logging adds to it."""
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    yield
    for handler in root.handlers[len(saved[0]) :]:
        handler.close()
    root.handlers[:], _ = saved
    root.setLevel(saved[1])


def lines_of(path):
    return path.read_text(encoding="utf-8").splitlines()


# --- timestamps ------------------------------------------------------------


def test_every_line_of_a_record_starts_with_unix_nanoseconds():
    formatter = TimestampedFormatter("%(levelname)s %(name)s: %(message)s")
    record = logging.LogRecord(
        "plexdo", logging.DEBUG, __file__, 1, "one\ntwo\n\nfour", None, None
    )
    lines = formatter.format(record).split("\n")
    assert len(lines) == 4
    assert all(STAMPED.match(line) for line in lines)
    stamp = int(lines[0].split()[0])
    assert 1.7e18 < stamp < 4e18  # nanoseconds, not seconds or millis
    assert lines[0].endswith("DEBUG plexdo: one")


# --- redaction -------------------------------------------------------------


@pytest.mark.parametrize(
    "text, hidden, kept",
    [
        ("GET /a?X-Plex-Token=abc123&x=1", "abc123", "x=1"),
        ("{'X-Plex-Token': 'abc123', 'Accept': 'xml'}", "abc123", "xml"),
        ('{"authToken":"abc123","id":5}', "abc123", '"id":5'),
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz", "Authorization"),
        ("https://bob:hunter2@plex.tv/api", "hunter2", "bob"),
        ("/api/home/users/7/switch?pin=1234", "1234", "users/7"),
        ("password=letmein&login=bob", "letmein", "login=bob"),
    ],
)
def test_named_secrets_are_redacted(text, hidden, kept):
    out = redact(text)
    assert hidden not in out
    assert "***" in out
    assert kept in out


def test_ordinary_text_is_left_alone():
    text = "transcode=1 status=200 ratingKey=1234 Secrets are kept in a file"
    assert redact(text) == text


def test_a_secret_met_once_is_hidden_wherever_it_appears():
    hide_in_logs("unnamed-secret-value-1")
    assert redact("someone logged unnamed-secret-value-1 bare") == (
        "someone logged *** bare"
    )


def test_a_short_value_is_not_hunted_for_everywhere():
    """A four-digit PIN would otherwise blank out every matching number."""
    hide_in_logs("4321")
    assert redact("ratingKey 4321") == "ratingKey 4321"


def test_a_request_hides_its_token_and_basic_password():
    credential = base64.b64encode(b"bob:a-long-password").decode()
    hide_request_secrets(
        "https://plex.tv/api?X-Plex-Token=query-token-value",
        {"Authorization": f"Basic {credential}", "Accept": "json"},
    )
    out = redact(f"query-token-value {credential} a-long-password")
    assert out == "*** *** ***"


def test_a_saved_secret_is_hidden_once_saved():
    secret_store.save("tokens", {"bob": "token-from-the-store"})
    assert redact("x token-from-the-store y") == "x *** y"


# --- configure_logging ------------------------------------------------------


def test_debug_goes_to_the_file_and_not_to_stderr(
    root_handlers, tmp_path, capsys
):
    log = tmp_path / "run.log"
    configure_logging(verbose=False, debug=True, debug_log=str(log))
    logging.getLogger("plexdo").debug("detail X-Plex-Token=abc123")
    logging.getLogger("plexdo").warning("a warning")
    err = capsys.readouterr().err
    assert "detail" not in err
    assert "a warning" in err
    lines = lines_of(log)
    assert any(
        line.endswith("DEBUG plexdo: detail X-Plex-Token=***") for line in lines
    )
    assert all(STAMPED.match(line) for line in lines)


def test_the_file_is_appended_to(root_handlers, tmp_path):
    log = tmp_path / "run.log"
    log.write_text("1 earlier run\n", encoding="utf-8")
    configure_logging(verbose=False, debug=False, debug_log=str(log))
    logging.getLogger("plexdo").debug("this run")
    assert lines_of(log)[0] == "1 earlier run"
    assert lines_of(log)[-1].endswith("this run")


@pytest.mark.skipif(os.name == "nt", reason="POSIX modes")
def test_a_new_file_is_readable_by_its_owner_alone(root_handlers, tmp_path):
    log = tmp_path / "run.log"
    configure_logging(verbose=False, debug=False, debug_log=str(log))
    assert log.stat().st_mode & 0o777 == 0o600


def test_an_unwritable_path_is_an_error_naming_it(root_handlers, tmp_path):
    with pytest.raises(SystemExit, match="Cannot open the debug log"):
        configure_logging(
            verbose=False, debug=False, debug_log=str(tmp_path / "no/such.log")
        )


def test_stderr_redacts_too(root_handlers, capsys):
    configure_logging(verbose=False, debug=True)
    logging.getLogger("plexdo").debug("GET /x?X-Plex-Token=abc123")
    assert "abc123" not in capsys.readouterr().err


# --- profiling --------------------------------------------------------------


class FakeAdapter(BaseAdapter):
    """Answers every request locally, or fails it, without a network."""

    def __init__(self, fail=False):
        super().__init__()
        self.fail = fail

    def send(self, request, **kwargs):  # pylint: disable=arguments-differ
        if self.fail:
            raise requests.ConnectionError("no route to host")
        response = requests.Response()
        response.status_code = 200
        response.reason = "OK"
        response.headers["Content-Type"] = "text/xml"
        response.headers["Set-Cookie"] = "session=cookie-value-123"
        response._content = b"<MediaContainer/>"  # pylint: disable=protected-access
        response.url = request.url
        response.request = request
        return response

    def close(self):
        pass


def session_with(adapter):
    session = requests.Session()
    session.mount("http://", adapter)
    return session


@pytest.fixture
def debug_log(root_handlers, tmp_path, monkeypatch):
    """A debug log for the test, and the lines written to it."""
    monkeypatch.setattr(profiling, "SAMPLE_SECONDS", 0.01)
    log = tmp_path / "run.log"
    configure_logging(verbose=False, debug=False, debug_log=str(log))
    return log


def test_a_request_is_logged_timed_and_redacted(debug_log):
    original = requests.Session.send
    with profiling.profiled(True, "list-users"):
        with profiling.span("command:list-users"):
            session_with(FakeAdapter()).get(
                "http://plex.lan:32400/accounts",
                headers={"X-Plex-Token": "header-token-123"},
            )
    assert requests.Session.send is original
    text = debug_log.read_text(encoding="utf-8")
    assert "header-token-123" not in text
    assert "cookie-value-123" not in text
    sent = next(line for line in lines_of(debug_log) if " send id=1 " in line)
    assert "method=GET url=http://plex.lan:32400/accounts bytes=0" in sent
    assert '"X-Plex-Token": "***"' in sent
    got = next(line for line in lines_of(debug_log) if " recv id=1 " in line)
    assert re.search(r"status=200 reason=\"OK\" wait_ns=\d+ ", got)
    assert "bytes=17 type=text/xml" in got
    span = next(line for line in lines_of(debug_log) if " span " in line)
    assert "name=command:list-users" in span
    assert "api_calls=1" in span
    end = next(line for line in lines_of(debug_log) if " run end " in line)
    assert "status=0" in end and "api_calls=1" in end
    assert "slowest_api=GET http://plex.lan:32400/accounts" in end


def test_a_failed_request_is_logged_and_still_raised(debug_log):
    with pytest.raises(requests.ConnectionError):
        with profiling.profiled(True, "status"):
            session_with(FakeAdapter(fail=True)).get("http://plex.lan/")
    failed = next(line for line in lines_of(debug_log) if " fail id=1 " in line)
    assert "error=ConnectionError: no route to host" in failed
    end = next(line for line in lines_of(debug_log) if " run end " in line)
    assert "status=exception:ConnectionError" in end
    assert "api_calls=1" in end


@pytest.mark.parametrize(
    "exc, status",
    [
        (SystemExit(None), "0"),
        (SystemExit(2), "2"),
        (SystemExit("No plex: url"), "1"),
        (KeyboardInterrupt(), "interrupted"),
    ],
)
def test_the_run_end_line_gives_the_exit_status(debug_log, exc, status):
    with pytest.raises(type(exc)):
        with profiling.profiled(True, "status"):
            raise exc
    end = next(line for line in lines_of(debug_log) if " run end " in line)
    assert f"status={status} " in end


def test_the_run_records_resources_and_function_times(debug_log):
    with profiling.profiled(True, "status"):
        profiling.time.sleep(0.05)
    lines = lines_of(debug_log)
    start = next(line for line in lines if " run start " in line)
    assert "command=status" in start and "plexapi=" in start
    sample = next(line for line in lines if " resources " in line)
    assert re.search(r"cpu_ns=\d+ .* cpu_percent=[\d.]+ rss_bytes=", sample)
    assert any("functions by cumulative time" in line for line in lines)
    assert any("functions by own time" in line for line in lines)


def test_without_a_debug_log_nothing_is_profiled():
    original = requests.Session.send
    with profiling.profiled(False, "status"), profiling.span("connect"):
        assert requests.Session.send is original
        assert profiling.Run.current is None


def test_usage_reads_the_clocks_and_memory():
    now = profiling.usage()
    assert now.cpu_ns > 0 and now.wall_ns > 0
    if os.name == "nt" or os.path.exists("/proc/self/statm"):
        assert now.rss_bytes and now.rss_bytes > 0
    if now.rss_bytes and now.peak_rss_bytes:
        assert now.peak_rss_bytes >= now.rss_bytes
