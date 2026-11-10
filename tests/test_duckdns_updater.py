import contextlib
import http.client
import io
import socket
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from scripts import duckdns_updater as updater


class Response:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    def read(self, limit):
        return self.body[:limit]


class Connection:
    def __init__(self, host, timeout, status=200, body=b"OK"):
        self.host, self.timeout = host, timeout
        self.response = Response(status, body)
        self.closed = False

    def request(self, method, path):
        self.method, self.path = method, path

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class UpdaterTests(unittest.TestCase):
    def test_ipv4_resolution_and_retry(self):
        addresses = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.2", 443)),
        ]
        sentinel = object()
        with patch.object(updater.socket, "getaddrinfo", return_value=addresses) as resolve, \
             patch.object(updater.socket, "create_connection", side_effect=[OSError(), sentinel]) as connect:
            self.assertIs(updater.connect_ipv4(("example.invalid", 443), 20), sentinel)
        resolve.assert_called_once_with("example.invalid", 443, socket.AF_INET, socket.SOCK_STREAM)
        self.assertEqual(connect.call_count, 2)

    def test_request_uses_only_ipv4_parameters_and_short_domain(self):
        connection = Connection(updater.HOST, updater.TIMEOUT)
        result = updater.update("Formation.duckdns.org", "dummy+token", lambda *a, **kw: connection)
        self.assertTrue(result)
        self.assertEqual(connection.host, "www.duckdns.org")
        self.assertEqual(connection.method, "GET")
        self.assertEqual(urlsplit(connection.path).path, "/update")
        self.assertEqual(parse_qs(urlsplit(connection.path).query, keep_blank_values=True),
                         {"domains": ["formation"], "token": ["dummy+token"], "ip": [""]})
        self.assertIs(connection._create_connection, updater.connect_ipv4)
        self.assertTrue(connection.closed)

    def test_rejected_and_http_error_responses(self):
        for status, body in [(200, b"KO"), (500, b"OK"), (302, b"OK"), (200, b"unexpected")]:
            with self.subTest(status=status, body=body):
                connection = Connection(updater.HOST, updater.TIMEOUT, status, body)
                self.assertFalse(updater.update("formation.duckdns.org", "dummy", lambda *a, **kw: connection))
                self.assertTrue(connection.closed)

    def test_invalid_configuration(self):
        for domain in ["duckdns.org", "foo.bar.duckdns.org", "-foo.duckdns.org", "foo.duckdns.org.evil", ""]:
            with self.subTest(domain=domain):
                with self.assertRaises(ValueError):
                    updater.update(domain, "dummy")
        with self.assertRaises(ValueError):
            updater.update("formation.duckdns.org", "")

    def test_loop_retries_without_printing_sensitive_exception(self):
        output = io.StringIO()
        with patch.object(updater, "update", side_effect=[OSError("dummy-secret"), False, True]), \
             patch.object(updater.time, "sleep", side_effect=[None, None, KeyboardInterrupt]) as sleep, \
             contextlib.redirect_stdout(output):
            with self.assertRaises(KeyboardInterrupt):
                updater.main()
        self.assertEqual(sleep.call_count, 3)
        self.assertTrue(all(call.args == (300,) for call in sleep.call_args_list))
        self.assertNotIn("dummy-secret", output.getvalue())
        self.assertIn("acceptée", output.getvalue())

    def test_connection_closed_on_network_error(self):
        connection = Connection(updater.HOST, updater.TIMEOUT)
        connection.getresponse = lambda: (_ for _ in ()).throw(http.client.HTTPException("dummy-secret"))
        with self.assertRaises(http.client.HTTPException):
            updater.update("formation.duckdns.org", "dummy", lambda *a, **kw: connection)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()