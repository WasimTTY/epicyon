__filename__ = "httpsig.py"
__author__ = "Bob Mottram"
__credits__ = ['lamia']
__license__ = "AGPL3+"
__version__ = "1.3.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Security"

# see https://tools.ietf.org/html/draft-cavage-http-signatures-06
#
# This might change in future
# see https://tools.ietf.org/html/draft-ietf-httpbis-message-signatures

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import utils as hazutils
import base64
from time import gmtime, strftime
import datetime
from utils import get_full_domain
from utils import get_sha_256
from utils import get_sha_512
from utils import local_actor_url


def message_content_digest(message_body_json_str: str,
                           digest_algorithm: str) -> str:
    """Returns the digest for the message body
    """
    msg = message_body_json_str.encode('utf-8')
    if digest_algorithm in ('rsa-sha512', 'rsa-pss-sha512'):
        hash_result = get_sha_512(msg)
    else:
        hash_result = get_sha_256(msg)
    return base64.b64encode(hash_result).decode('utf-8')


def get_digest_prefix(digest_algorithm: str) -> str:
    """Returns the prefix for the message body digest
    """
    if digest_algorithm in ('rsa-sha512', 'rsa-pss-sha512'):
        return 'SHA-512'
    return 'SHA-256'


def get_digest_algorithm_from_headers(http_headers: {}) -> str:
    """Returns the digest algorithm from http headers
    """
    digest_str = None
    if http_headers.get('digest'):
        digest_str = http_headers['digest']
    elif http_headers.get('Digest'):
        digest_str = http_headers['Digest']
    if digest_str:
        if digest_str.startswith('SHA-512'):
            return 'rsa-sha512'
    return 'rsa-sha256'


def sign_post_headers(dateStr: str, private_key_pem: str,
                      nickname: str, domain: str, port: int,
                      to_domain: str, to_port: int,
                      path: str, http_prefix: str,
                      message_body_json_str: str,
                      content_type: str, algorithm: str,
                      digest_algorithm: str) -> str:
    """Returns a raw signature string that can be plugged into a header and
    used to verify the authenticity of an HTTP transmission.
    """
    domain = get_full_domain(domain, port)

    to_domain = get_full_domain(to_domain, to_port)

    if not dateStr:
        dateStr = strftime("%a, %d %b %Y %H:%M:%S %Z", gmtime())
    if nickname != domain and nickname.lower() != 'actor':
        key_id = local_actor_url(http_prefix, nickname, domain)
    else:
        # instance actor
        key_id = http_prefix + '://' + domain + '/actor'
    key_id += '#main-key'
    if not message_body_json_str:
        headers = {
            '(request-target)': f'get {path}',
            'host': to_domain,
            'date': dateStr,
            'accept': content_type
        }
    else:
        body_digest = \
            message_content_digest(message_body_json_str, digest_algorithm)
        digest_prefix = get_digest_prefix(digest_algorithm)
        content_length = len(message_body_json_str)
        headers = {
            '(request-target)': f'post {path}',
            'host': to_domain,
            'date': dateStr,
            'digest': f'{digest_prefix}={body_digest}',
            'content-type': 'application/activity+json',
            'content-length': str(content_length)
        }
    key = load_pem_private_key(private_key_pem.encode('utf-8'),
                               None, backend=default_backend())
    # headers.update({
    #     '(request-target)': f'post {path}',
    # })
    # build a digest for signing
    signed_header_keys = headers.keys()
    signed_header_text = ''
    for header_key in signed_header_keys:
        signed_header_text += f'{header_key}: {headers[header_key]}\n'
    # strip the trailing linefeed
    signed_header_text = signed_header_text.rstrip('\n')
    # signed_header_text.encode('ascii') matches
    header_digest = get_sha_256(signed_header_text.encode('ascii'))
    # print('header_digest2: ' + str(header_digest))

    # Sign the digest
    raw_signature = key.sign(header_digest,
                             padding.PKCS1v15(),
                             hazutils.Prehashed(hashes.SHA256()))
    signature = base64.b64encode(raw_signature).decode('ascii')

    # Put it into a valid HTTP signature format
    signature_dict = {
        'keyId': key_id,
        'algorithm': algorithm,
        'headers': ' '.join(signed_header_keys),
        'signature': signature
    }
    signature_header = ','.join(
        [f'{k}="{v}"' for k, v in signature_dict.items()])
    return signature_header


def sign_post_headers_new(dateStr: str, private_key_pem: str,
                          nickname: str,
                          domain: str, port: int,
                          to_domain: str, to_port: int,
                          path: str,
                          http_prefix: str,
                          message_body_json_str: str,
                          algorithm: str, digest_algorithm: str,
                          debug: bool) -> (str, str):
    """Returns a raw signature strings that can be plugged into a header
    as "Signature-Input" and "Signature"
    used to verify the authenticity of an HTTP transmission.
    See https://tools.ietf.org/html/draft-ietf-httpbis-message-signatures
    """
    domain = get_full_domain(domain, port)

    to_domain = get_full_domain(to_domain, to_port)

    time_format = "%a, %d %b %Y %H:%M:%S %Z"
    if not dateStr:
        curr_time = gmtime()
        dateStr = strftime(time_format, curr_time)
    else:
        curr_time = datetime.datetime.strptime(dateStr, time_format)
    seconds_since_epoch = \
        int((curr_time - datetime.datetime(1970, 1, 1)).total_seconds())
    key_id = local_actor_url(http_prefix, nickname, domain) + '#main-key'
    if not message_body_json_str:
        headers = {
            '@request-target': f'get {path}',
            '@created': str(seconds_since_epoch),
            'host': to_domain,
            'date': dateStr
        }
    else:
        body_digest = message_content_digest(message_body_json_str,
                                             digest_algorithm)
        digest_prefix = get_digest_prefix(digest_algorithm)
        content_length = len(message_body_json_str)
        headers = {
            '@request-target': f'post {path}',
            '@created': str(seconds_since_epoch),
            'host': to_domain,
            'date': dateStr,
            'digest': f'{digest_prefix}={body_digest}',
            'content-type': 'application/activity+json',
            'content-length': str(content_length)
        }
    key = load_pem_private_key(private_key_pem.encode('utf-8'),
                               None, backend=default_backend())
    # build a digest for signing
    signed_header_keys = headers.keys()
    signed_header_text = ''
    for header_key in signed_header_keys:
        signed_header_text += f'{header_key}: {headers[header_key]}\n'
    signed_header_text = signed_header_text.strip()

    if debug:
        print('\nsign_post_headers_new signed_header_text:\n' +
              signed_header_text + '\nEND\n')

    # Sign the digest. Potentially other signing algorithms can be added here.
    signature = ''
    if algorithm == 'rsa-sha512':
        header_digest = get_sha_512(signed_header_text.encode('ascii'))
        raw_signature = key.sign(header_digest,
                                 padding.PKCS1v15(),
                                 hazutils.Prehashed(hashes.SHA512()))
        signature = base64.b64encode(raw_signature).decode('ascii')
    else:
        # default rsa-sha256
        header_digest = get_sha_256(signed_header_text.encode('ascii'))
        raw_signature = key.sign(header_digest,
                                 padding.PKCS1v15(),
                                 hazutils.Prehashed(hashes.SHA256()))
        signature = base64.b64encode(raw_signature).decode('ascii')

    sig_key = 'sig1'
    # Put it into a valid HTTP signature format
    signature_input_dict = {
        'keyId': key_id,
    }
    signature_index_header = '; '.join(
        [f'{k}="{v}"' for k, v in signature_input_dict.items()])
    signature_index_header += '; alg=hs2019'
    signature_index_header += '; created=' + str(seconds_since_epoch)
    signature_index_header += \
        '; ' + sig_key + '=(' + ', '.join(signed_header_keys) + ')'
    signature_dict = {
        sig_key: signature
    }
    signature_header = '; '.join(
        [f'{k}=:{v}:' for k, v in signature_dict.items()])
    return signature_index_header, signature_header


def create_signed_header(dateStr: str, private_key_pem: str, nickname: str,
                         domain: str, port: int,
                         to_domain: str, to_port: int,
                         path: str, http_prefix: str, withDigest: bool,
                         message_body_json_str: str,
                         content_type: str) -> {}:
    """Note that the domain is the destination, not the sender
    """
    algorithm = 'rsa-sha256'
    digest_algorithm = 'rsa-sha256'
    header_domain = get_full_domain(to_domain, to_port)

    # if no date is given then create one
    if not dateStr:
        dateStr = strftime("%a, %d %b %Y %H:%M:%S %Z", gmtime())

    # Content-Type or Accept header
    if not content_type:
        content_type = 'application/activity+json'

    if not withDigest:
        headers = {
            '(request-target)': f'get {path}',
            'host': header_domain,
            'date': dateStr,
            'accept': content_type
        }
        signature_header = \
            sign_post_headers(dateStr, private_key_pem, nickname,
                              domain, port, to_domain, to_port,
                              path, http_prefix, None, content_type,
                              algorithm, None)
    else:
        body_digest = message_content_digest(message_body_json_str,
                                             digest_algorithm)
        digest_prefix = get_digest_prefix(digest_algorithm)
        content_length = len(message_body_json_str)
        headers = {
            '(request-target)': f'post {path}',
            'host': header_domain,
            'date': dateStr,
            'digest': f'{digest_prefix}={body_digest}',
            'content-length': str(content_length),
            'content-type': content_type
        }
        signature_header = \
            sign_post_headers(dateStr, private_key_pem, nickname,
                              domain, port,
                              to_domain, to_port,
                              path, http_prefix, message_body_json_str,
                              content_type, algorithm, digest_algorithm)
    headers['signature'] = signature_header
    return headers


def _verify_recent_signature(signed_date_str: str) -> bool:
    """Checks whether the given time taken from the header is within
    12 hours of the current time
    """
    curr_date = datetime.datetime.utcnow()
    date_format = "%a, %d %b %Y %H:%M:%S %Z"
    signed_date = datetime.datetime.strptime(signed_date_str, date_format)
    time_diff_sec = (curr_date - signed_date).seconds
    # 12 hours tollerance
    if time_diff_sec > 43200:
        print('WARN: Header signed too long ago: ' + signed_date_str)
        print(str(time_diff_sec / (60 * 60)) + ' hours')
        return False
    if time_diff_sec < 0:
        print('WARN: Header signed in the future! ' + signed_date_str)
        print(str(time_diff_sec / (60 * 60)) + ' hours')
        return False
    return True


def verify_post_headers(http_prefix: str,
                        publicKeyPem: str, headers: dict,
                        path: str, GETmethod: bool,
                        messageBodyDigest: str,
                        message_body_json_str: str, debug: bool,
                        noRecencyCheck: bool = False) -> bool:
    """Returns true or false depending on if the key that we plugged in here
    validates against the headers, method, and path.
    publicKeyPem - the public key from an rsa key pair
    headers - should be a dictionary of request headers
    path - the relative url that was requested from this site
    GETmethod - GET or POST
    message_body_json_str - the received request body (used for digest)
    """

    if GETmethod:
        method = 'GET'
    else:
        method = 'POST'

    if debug:
        print('DEBUG: verify_post_headers ' + method)
        print('verify_post_headers publicKeyPem: ' + str(publicKeyPem))
        print('verify_post_headers headers: ' + str(headers))
        print('verify_post_headers message_body_json_str: ' +
              str(message_body_json_str))

    pubkey = load_pem_public_key(publicKeyPem.encode('utf-8'),
                                 backend=default_backend())
    # Build a dictionary of the signature values
    if headers.get('Signature-Input') or headers.get('signature-input'):
        if headers.get('Signature-Input'):
            signature_header = headers['Signature-Input']
        else:
            signature_header = headers['signature-input']
        field_sep2 = ','
        # split the signature input into separate fields
        signature_dict = {
            k.strip(): v.strip()
            for k, v in [i.split('=', 1) for i in signature_header.split(';')]
        }
        request_target_key = None
        request_target_str = None
        for key_str, value_str in signature_dict.items():
            if value_str.startswith('('):
                request_target_key = key_str
                request_target_str = value_str[1:-1]
            elif value_str.startswith('"'):
                signature_dict[key_str] = value_str[1:-1]
        if not request_target_key:
            return False
        signature_dict[request_target_key] = request_target_str
    else:
        request_target_key = 'headers'
        signature_header = headers['signature']
        field_sep2 = ' '
        # split the signature input into separate fields
        signature_dict = {
            k: v[1:-1]
            for k, v in [i.split('=', 1) for i in signature_header.split(',')]
        }

    if debug:
        print('signature_dict: ' + str(signature_dict))

    # Unpack the signed headers and set values based on current headers and
    # body (if a digest was included)
    signed_header_list = []
    algorithm = 'rsa-sha256'
    digest_algorithm = 'rsa-sha256'
    for signed_header in signature_dict[request_target_key].split(field_sep2):
        signed_header = signed_header.strip()
        if debug:
            print('DEBUG: verify_post_headers signed_header=' + signed_header)
        if signed_header == '(request-target)':
            # original Mastodon http signature
            append_str = f'(request-target): {method.lower()} {path}'
            signed_header_list.append(append_str)
        elif '@request-target' in signed_header:
            # https://tools.ietf.org/html/
            # draft-ietf-httpbis-message-signatures
            append_str = f'@request-target: {method.lower()} {path}'
            signed_header_list.append(append_str)
        elif '@created' in signed_header:
            if signature_dict.get('created'):
                created_str = str(signature_dict['created'])
                append_str = f'@created: {created_str}'
                signed_header_list.append(append_str)
        elif '@expires' in signed_header:
            if signature_dict.get('expires'):
                expires_str = str(signature_dict['expires'])
                append_str = f'@expires: {expires_str}'
                signed_header_list.append(append_str)
        elif '@method' in signed_header:
            append_str = f'@expires: {method}'
            signed_header_list.append(append_str)
        elif '@scheme' in signed_header:
            signed_header_list.append('@scheme: http')
        elif '@authority' in signed_header:
            authority_str = None
            if signature_dict.get('authority'):
                authority_str = str(signature_dict['authority'])
            elif signature_dict.get('Authority'):
                authority_str = str(signature_dict['Authority'])
            if authority_str:
                append_str = f'@authority: {authority_str}'
                signed_header_list.append(append_str)
        elif signed_header == 'algorithm':
            if headers.get(signed_header):
                algorithm = headers[signed_header]
                if debug:
                    print('http signature algorithm: ' + algorithm)
        elif signed_header == 'digest':
            if messageBodyDigest:
                body_digest = messageBodyDigest
            else:
                body_digest = \
                    message_content_digest(message_body_json_str,
                                           digest_algorithm)
            signed_header_list.append(f'digest: SHA-256={body_digest}')
        elif signed_header == 'content-length':
            if headers.get(signed_header):
                append_str = f'content-length: {headers[signed_header]}'
                signed_header_list.append(append_str)
            elif headers.get('Content-Length'):
                content_length = headers['Content-Length']
                signed_header_list.append(f'content-length: {content_length}')
            elif headers.get('Content-length'):
                content_length = headers['Content-length']
                append_str = f'content-length: {content_length}'
                signed_header_list.append(append_str)
            else:
                if debug:
                    print('DEBUG: verify_post_headers ' + signed_header +
                          ' not found in ' + str(headers))
        else:
            if headers.get(signed_header):
                if signed_header == 'date' and not noRecencyCheck:
                    if not _verify_recent_signature(headers[signed_header]):
                        if debug:
                            print('DEBUG: ' +
                                  'verify_post_headers date is not recent ' +
                                  headers[signed_header])
                        return False
                signed_header_list.append(
                    f'{signed_header}: {headers[signed_header]}')
            else:
                if '-' in signed_header:
                    # capitalise with dashes
                    # my-header becomes My-Header
                    header_parts = signed_header.split('-')
                    signed_header_cap = None
                    for part in header_parts:
                        if signed_header_cap:
                            signed_header_cap += '-' + part.capitalize()
                        else:
                            signed_header_cap = part.capitalize()
                else:
                    # header becomes Header
                    signed_header_cap = signed_header.capitalize()

                if debug:
                    print('signed_header_cap: ' + signed_header_cap)

                # if this is the date header then check it is recent
                if signed_header_cap == 'Date':
                    signed_hdr_cap = headers[signed_header_cap]
                    if not _verify_recent_signature(signed_hdr_cap):
                        if debug:
                            print('DEBUG: ' +
                                  'verify_post_headers date is not recent ' +
                                  headers[signed_header])
                        return False

                # add the capitalised header
                if headers.get(signed_header_cap):
                    signed_header_list.append(
                        f'{signed_header}: {headers[signed_header_cap]}')
                elif '-' in signed_header:
                    # my-header becomes My-header
                    signed_header_cap = signed_header.capitalize()
                    if headers.get(signed_header_cap):
                        signed_header_list.append(
                            f'{signed_header}: {headers[signed_header_cap]}')

    # Now we have our header data digest
    signed_header_text = '\n'.join(signed_header_list)
    if debug:
        print('\nverify_post_headers signed_header_text:\n' +
              signed_header_text + '\nEND\n')

    # Get the signature, verify with public key, return result
    if (headers.get('Signature-Input') and headers.get('Signature')) or \
       (headers.get('signature-input') and headers.get('signature')):
        # https://tools.ietf.org/html/
        # draft-ietf-httpbis-message-signatures
        if headers.get('Signature'):
            headers_sig = headers['Signature']
        else:
            headers_sig = headers['signature']
        # remove sig1=:
        if request_target_key + '=:' in headers_sig:
            headers_sig = headers_sig.split(request_target_key + '=:')[1]
            headers_sig = headers_sig[:len(headers_sig)-1]
        signature = base64.b64decode(headers_sig)
    else:
        # Original Mastodon signature
        headers_sig = signature_dict['signature']
        signature = base64.b64decode(headers_sig)
    if debug:
        print('signature: ' + algorithm + ' ' + headers_sig)

    # log unusual signing algorithms
    if signature_dict.get('alg'):
        print('http signature algorithm: ' + signature_dict['alg'])

    # If extra signing algorithms need to be added then do it here
    if not signature_dict.get('alg'):
        alg = hazutils.Prehashed(hashes.SHA256())
    elif (signature_dict['alg'] == 'rsa-sha256' or
          signature_dict['alg'] == 'rsa-v1_5-sha256' or
          signature_dict['alg'] == 'hs2019'):
        alg = hazutils.Prehashed(hashes.SHA256())
    elif (signature_dict['alg'] == 'rsa-sha512' or
          signature_dict['alg'] == 'rsa-pss-sha512'):
        alg = hazutils.Prehashed(hashes.SHA512())
    else:
        alg = hazutils.Prehashed(hashes.SHA256())

    if digest_algorithm == 'rsa-sha256':
        header_digest = get_sha_256(signed_header_text.encode('ascii'))
    elif digest_algorithm == 'rsa-sha512':
        header_digest = get_sha_512(signed_header_text.encode('ascii'))
    else:
        print('Unknown http digest algorithm: ' + digest_algorithm)
        header_digest = ''
    padding_str = padding.PKCS1v15()

    try:
        pubkey.verify(signature, header_digest, padding_str, alg)
        return True
    except BaseException:
        if debug:
            print('EX: verify_post_headers pkcs1_15 verify failure')
    return False
