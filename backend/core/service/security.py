"""Loopback host/origin and session-token checks shared by HTTP routes."""
import secrets


def allowed_host(headers, port):
    return headers.get('Host') in {f'127.0.0.1:{port}', f'localhost:{port}'}


def allowed_write(headers, port, token):
    origin = headers.get('Origin')
    expected = f'http://{headers.get("Host", "")}'
    supplied = headers.get('X-Miao-Token', '')
    return (allowed_host(headers, port) and secrets.compare_digest(supplied.encode('utf-8'), token.encode('utf-8'))
            and (not origin or origin == expected) and headers.get('Sec-Fetch-Site') != 'cross-site')
