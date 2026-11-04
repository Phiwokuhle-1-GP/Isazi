"""Parse referral identifiers locally; never request a pasted URL."""
import re
from urllib.parse import unquote, urlsplit

CODE = r'[A-Z0-9][A-Z0-9_-]{2,23}'
BUYER_DISCOUNT_BPS = 500


def parse_code(value):
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if not value or len(value) > 500 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        return ''
    if value.isascii() and re.fullmatch(CODE, value.upper(), re.ASCII):
        return value.upper()
    try:
        link = urlsplit(value)
        if link.scheme:
            if link.scheme.lower() not in ('http', 'https') or not link.hostname or link.username or link.password:
                return ''
        elif link.netloc or not value.startswith('/r/'):
            return ''
        path = unquote(link.path)
        if not path.isascii():
            return ''
        match = re.fullmatch('/r/(' + CODE + ')/?', path, re.ASCII | re.IGNORECASE)
        return match.group(1).upper() if match else ''
    except ValueError:
        return ''
