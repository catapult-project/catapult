'''These tests rely on replies from public internet services

TODO: reimplement with local stubs
'''
import httplib2
import os
import pytest
import ssl
import sys
import tests


def test_get_301_via_https():
    # Google always redirects to http://google.com
    http = httplib2.Http()
    response, content = http.request('https://code.google.com/apis/', 'GET')
    assert response.status == 200
    assert response.previous.status == 301


def test_get_via_https():
    # Test that we can handle HTTPS
    http = httplib2.Http()
    response, content = http.request('https://google.com/adsense/', 'GET')
    assert response.status == 200


def test_get_via_https_spec_violation_on_location():
    # Test that we follow redirects through HTTPS
    # even if they violate the spec by including
    # a relative Location: header instead of an
    # absolute one.
    http = httplib2.Http()
    response, content = http.request('https://google.com/adsense', 'GET')
    assert response.status == 200
    assert response.previous is not None


def test_get_via_https_key_cert():
    #  At this point I can only test
    #  that the key and cert files are passed in
    #  correctly to httplib. It would be nice to have
    #  a real https endpoint to test against.
    http = httplib2.Http(timeout=2)
    http.add_certificate('akeyfile', 'acertfile', 'bitworking.org')
    try:
        http.request('https://bitworking.org', 'GET')
    except AttributeError:
        assert http.connections['https:bitworking.org'].key_file == 'akeyfile'
        assert http.connections['https:bitworking.org'].cert_file == 'acertfile'
    except IOError:
        # Skip on 3.2
        pass

    try:
        http.request('https://notthere.bitworking.org', 'GET')
    except httplib2.ServerNotFoundError:
        assert http.connections['https:notthere.bitworking.org'].key_file is None
        assert http.connections['https:notthere.bitworking.org'].cert_file is None
    except IOError:
        # Skip on 3.2
        pass


def test_ssl_invalid_ca_certs_path():
    # Test that we get an ssl.SSLError when specifying a non-existent CA
    # certs file.
    http = httplib2.Http(ca_certs='/nosuchfile')
    with tests.assert_raises(IOError):
        http.request('https://www.google.com/', 'GET')


@pytest.mark.xfail(
    sys.version_info <= (3,),
    reason='FIXME: for unknown reason Python 2.7.10 validates www.google.com against dummy CA www.example.com',
)
def test_ssl_wrong_ca():
    # Test that we get a SSLHandshakeError if we try to access
    # https://www.google.com, using a CA cert file that doesn't contain
    # the CA Google uses (i.e., simulating a cert that's not signed by a
    # trusted CA).
    other_ca_certs = os.path.join(
        os.path.dirname(os.path.abspath(httplib2.__file__)),
        'test', 'other_cacerts.txt')
    assert os.path.exists(other_ca_certs)
    http = httplib2.Http(ca_certs=other_ca_certs)
    http.follow_redirects = False
    with tests.assert_raises(ssl.SSLError):
        http.request('https://www.google.com/', 'GET')


def test_sni_hostname_validation():
    # TODO: make explicit test server with SNI validation
    http = httplib2.Http()
    http.request('https://google.com/', method='GET')
