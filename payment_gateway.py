"""PayFast hosted checkout helpers. Never accept a browser return as proof of payment.
Reference: https://developers.payfast.co.za/docs/itn-instant-transaction-notification/
"""
import hashlib
import hmac
import ipaddress
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

PAYFAST_NETWORKS = ('197.97.145.144/28', '41.74.179.192/27', '102.216.36.0/28', '102.216.36.128/28', '144.126.193.139/32')


def encode(value):
    # PHP urlencode encodes tilde; quote_plus leaves it unescaped by default.
    return urllib.parse.quote_plus(str(value), safe='').replace('~', '%7E')


def parameter_string(pairs, *, skip_blank=False, trim=False):
    parts = []
    for key, value in pairs:
        if key == 'signature':
            continue
        value = str(value).strip() if trim else str(value)
        if skip_blank and value == '':
            continue
        parts.append(encode(key) + '=' + encode(value))
    return '&'.join(parts)


def signature(pairs, passphrase, *, outgoing=False):
    value = parameter_string(pairs, skip_blank=outgoing, trim=outgoing)
    if passphrase:
        value += '&passphrase=' + encode(passphrase.strip())
    return hashlib.md5(value.encode('utf-8')).hexdigest()


def valid_signature(pairs, supplied, passphrase):
    return isinstance(supplied, str) and len(supplied) == 32 and supplied.isascii() and hmac.compare_digest(signature(pairs, passphrase), supplied.lower())


def cents(raw):
    try:
        value = Decimal(str(raw))
        if not value.is_finite() or value < 0 or value > Decimal('10000000') or value != value.quantize(Decimal('.01')):
            raise ValueError
        return int(value * 100)
    except (ValueError, InvalidOperation, TypeError):
        raise ValueError('Enter a valid amount with no more than two decimal places.')


def network_contains(address, networks):
    try:
        ip = ipaddress.ip_address(address)
        return any(ip in ipaddress.ip_network(net.strip()) for net in networks if net.strip())
    except ValueError:
        return False


def source_ip(request, trusted_proxies=()):
    address = request.remote_addr or ''
    if trusted_proxies and network_contains(address, trusted_proxies):
        chain = [p.strip() for p in request.headers.get('X-Forwarded-For', '').split(',') if p.strip()] + [address]
        for hop in reversed(chain):
            if not network_contains(hop, trusted_proxies):
                return hop
    return address


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def server_validates(param_string, mode):
    host = 'sandbox.payfast.co.za' if mode == 'sandbox' else 'www.payfast.co.za'
    request = urllib.request.Request('https://' + host + '/eng/query/validate', data=param_string.encode(), headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Isazi-Shop/2.5'}, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=12) as response:
            return response.status == 200 and response.read(1024).decode('utf-8').strip() == 'VALID'
    except (OSError, urllib.error.URLError, UnicodeError):
        return False
