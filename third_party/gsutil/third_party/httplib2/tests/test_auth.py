import httplib2
import pytest
import tests
from six.moves import urllib


def test_credentials():
    c = httplib2.Credentials()
    c.add("joe", "password")
    assert tuple(c.iter("bitworking.org"))[0] == ("joe", "password")
    assert tuple(c.iter(""))[0] == ("joe", "password")
    c.add("fred", "password2", "wellformedweb.org")
    assert tuple(c.iter("bitworking.org"))[0] == ("joe", "password")
    assert len(tuple(c.iter("bitworking.org"))) == 1
    assert len(tuple(c.iter("wellformedweb.org"))) == 2
    assert ("fred", "password2") in tuple(c.iter("wellformedweb.org"))
    c.clear()
    assert len(tuple(c.iter("bitworking.org"))) == 0
    c.add("fred", "password2", "wellformedweb.org")
    assert ("fred", "password2") in tuple(c.iter("wellformedweb.org"))
    assert len(tuple(c.iter("bitworking.org"))) == 0
    assert len(tuple(c.iter(""))) == 0


def test_basic():
    # Test Basic Authentication
    http = httplib2.Http()
    password = tests.gen_password()
    handler = tests.http_reflect_with_auth(
        allow_scheme="basic", allow_credentials=(("joe", password),)
    )
    with tests.server_request(handler, request_count=3) as uri:
        response, content = http.request(uri, "GET")
        assert response.status == 401
        http.add_credentials("joe", password)
        response, content = http.request(uri, "GET")
        assert response.status == 200


def test_basic_for_domain():
    # Test Basic Authentication
    http = httplib2.Http()
    password = tests.gen_password()
    handler = tests.http_reflect_with_auth(
        allow_scheme="basic", allow_credentials=(("joe", password),)
    )
    with tests.server_request(handler, request_count=4) as uri:
        response, content = http.request(uri, "GET")
        assert response.status == 401
        http.add_credentials("joe", password, "example.org")
        response, content = http.request(uri, "GET")
        assert response.status == 401
        domain = urllib.parse.urlparse(uri)[1]
        http.add_credentials("joe", password, domain)
        response, content = http.request(uri, "GET")
        assert response.status == 200


def test_basic_two_credentials():
    # Test Basic Authentication with multiple sets of credentials
    http = httplib2.Http()
    password1 = tests.gen_password()
    password2 = tests.gen_password()
    allowed = [("joe", password1)]  # exploit shared mutable list
    handler = tests.http_reflect_with_auth(
        allow_scheme="basic", allow_credentials=allowed
    )
    with tests.server_request(handler, request_count=7) as uri:
        http.add_credentials("fred", password2)
        response, content = http.request(uri, "GET")
        assert response.status == 401
        http.add_credentials("joe", password1)
        response, content = http.request(uri, "GET")
        assert response.status == 200
        allowed[0] = ("fred", password2)
        response, content = http.request(uri, "GET")
        assert response.status == 200


def test_digest():
    # Test that we support Digest Authentication
    http = httplib2.Http()
    password = tests.gen_password()
    handler = tests.http_reflect_with_auth(
        allow_scheme="digest", allow_credentials=(("joe", password),)
    )
    with tests.server_request(handler, request_count=3) as uri:
        response, content = http.request(uri, "GET")
        assert response.status == 401
        http.add_credentials("joe", password)
        response, content = http.request(uri, "GET")
        assert response.status == 200, content.decode()


def test_digest_next_nonce_nc():
    # Test that if the server sets nextnonce that we reset
    # the nonce count back to 1
    http = httplib2.Http()
    password = tests.gen_password()
    grenew_nonce = [None]
    handler = tests.http_reflect_with_auth(
        allow_scheme="digest",
        allow_credentials=(("joe", password),),
        out_renew_nonce=grenew_nonce,
    )
    with tests.server_request(handler, request_count=5) as uri:
        http.add_credentials("joe", password)
        response1, _ = http.request(uri, "GET")
        info = httplib2._parse_www_authenticate(response1, "authentication-info")
        assert response1.status == 200
        assert info.get("digest", {}).get("nc") == "00000001", info
        assert not info.get("digest", {}).get("nextnonce"), info
        response2, _ = http.request(uri, "GET")
        info2 = httplib2._parse_www_authenticate(response2, "authentication-info")
        assert info2.get("digest", {}).get("nc") == "00000002", info2
        grenew_nonce[0]()
        response3, content = http.request(uri, "GET")
        info3 = httplib2._parse_www_authenticate(response3, "authentication-info")
        assert response3.status == 200
        assert info3.get("digest", {}).get("nc") == "00000001", info3


def test_digest_auth_stale():
    # Test that we can handle a nonce becoming stale
    http = httplib2.Http()
    password = tests.gen_password()
    grenew_nonce = [None]
    requests = []
    handler = tests.http_reflect_with_auth(
        allow_scheme="digest",
        allow_credentials=(("joe", password),),
        out_renew_nonce=grenew_nonce,
        out_requests=requests,
    )
    with tests.server_request(handler, request_count=4) as uri:
        http.add_credentials("joe", password)
        response, _ = http.request(uri, "GET")
        assert response.status == 200
        info = httplib2._parse_www_authenticate(
            requests[0][1].headers, "www-authenticate"
        )
        grenew_nonce[0]()
        response, _ = http.request(uri, "GET")
        assert response.status == 200
        assert not response.fromcache
        assert getattr(response, "_stale_digest", False)
        info2 = httplib2._parse_www_authenticate(
            requests[2][1].headers, "www-authenticate"
        )
        nonce1 = info.get("digest", {}).get("nonce", "")
        nonce2 = info2.get("digest", {}).get("nonce", "")
        assert nonce1 != ""
        assert nonce2 != ""
        assert nonce1 != nonce2, (nonce1, nonce2)


@pytest.mark.parametrize(
    "data",
    (
        ({}, {}),
        ({"www-authenticate": ""}, {}),
        (
            {
                "www-authenticate": 'Test realm="test realm" , foo=foo ,bar="bar", baz=baz,qux=qux'
            },
            {
                "test": {
                    "realm": "test realm",
                    "foo": "foo",
                    "bar": "bar",
                    "baz": "baz",
                    "qux": "qux",
                }
            },
        ),
        (
            {"www-authenticate": 'T*!%#st realm=to*!%#en, to*!%#en="quoted string"'},
            {"t*!%#st": {"realm": "to*!%#en", "to*!%#en": "quoted string"}},
        ),
        (
            {"www-authenticate": 'Test realm="a \\"test\\" realm"'},
            {"test": {"realm": 'a "test" realm'}},
        ),
        ({"www-authenticate": 'Basic realm="me"'}, {"basic": {"realm": "me"}}),
        (
            {"www-authenticate": 'Basic realm="me", algorithm="MD5"'},
            {"basic": {"realm": "me", "algorithm": "MD5"}},
        ),
        (
            {"www-authenticate": 'Basic realm="me", algorithm=MD5'},
            {"basic": {"realm": "me", "algorithm": "MD5"}},
        ),
        (
            {"www-authenticate": 'Basic realm="me",other="fred" '},
            {"basic": {"realm": "me", "other": "fred"}},
        ),
        ({"www-authenticate": 'Basic REAlm="me" '}, {"basic": {"realm": "me"}}),
        (
            {
                "www-authenticate": 'Digest realm="digest1", qop="auth,auth-int", nonce="7102dd2", opaque="e9517f"'
            },
            {
                "digest": {
                    "realm": "digest1",
                    "qop": "auth,auth-int",
                    "nonce": "7102dd2",
                    "opaque": "e9517f",
                }
            },
        ),
        # multiple schema choice
        (
            {
                "www-authenticate": 'Digest realm="multi-d", nonce="8b11d0f6", opaque="cc069c" Basic realm="multi-b" '
            },
            {
                "digest": {"realm": "multi-d", "nonce": "8b11d0f6", "opaque": "cc069c"},
                "basic": {"realm": "multi-b"},
            },
        ),
        # FIXME
        # comma between schemas (glue for multiple headers with same name)
        # ({'www-authenticate': 'Digest realm="2-comma-d", qop="auth-int", nonce="c0c8ff1", Basic realm="2-comma-b"'},
        #  {'digest': {'realm': '2-comma-d', 'qop': 'auth-int', 'nonce': 'c0c8ff1'},
        #   'basic': {'realm': '2-comma-b'}}),
        # FIXME
        # comma between schemas + WSSE (glue for multiple headers with same name)
        # ({'www-authenticate': 'Digest realm="com3d", Basic realm="com3b", WSSE realm="com3w", profile="token"'},
        #  {'digest': {'realm': 'com3d'}, 'basic': {'realm': 'com3b'}, 'wsse': {'realm': 'com3w', profile': 'token'}}),
        # FIXME
        # multiple syntax figures
        # ({'www-authenticate':
        #     'Digest realm="brig", qop \t=\t"\tauth,auth-int", nonce="(*)&^&$%#",opaque="5ccc"' +
        #     ', Basic REAlm="zoo", WSSE realm="very", profile="UsernameToken"'},
        #  {'digest': {'realm': 'brig', 'qop': 'auth,auth-int', 'nonce': '(*)&^&$%#', 'opaque': '5ccc'},
        #   'basic': {'realm': 'zoo'},
        #   'wsse': {'realm': 'very', 'profile': 'UsernameToken'}}),
        # more quote combos
        (
            {
                "www-authenticate": 'Digest realm="myrealm", nonce="KBAA=3", algorithm=MD5, qop="auth", stale=true'
            },
            {
                "digest": {
                    "realm": "myrealm",
                    "nonce": "KBAA=3",
                    "algorithm": "MD5",
                    "qop": "auth",
                    "stale": "true",
                }
            },
        ),
    ),
    ids=lambda data: str(data[0]),
)
@pytest.mark.parametrize("strict", (True, False), ids=("strict", "relax"))
def test_parse_www_authenticate_correct(data, strict):
    headers, info = data
    # FIXME: move strict to parse argument
    httplib2.USE_WWW_AUTH_STRICT_PARSING = strict
    try:
        assert httplib2._parse_www_authenticate(headers) == info
    finally:
        httplib2.USE_WWW_AUTH_STRICT_PARSING = 0


def test_parse_www_authenticate_malformed():
    # TODO: test (and fix) header value 'barbqwnbm-bb...:asd' leads to dead loop
    with tests.assert_raises(httplib2.MalformedHeader):
        httplib2._parse_www_authenticate(
            {
                "www-authenticate": 'OAuth "Facebook Platform" "invalid_token" "Invalid OAuth access token."'
            }
        )


def test_digest_object():
    credentials = ("joe", "password")
    host = None
    request_uri = "/test/digest/"
    headers = {}
    response = {
        "www-authenticate": 'Digest realm="myrealm", nonce="KBAA=35", algorithm=MD5, qop="auth"'
    }
    content = b""

    d = httplib2.DigestAuthentication(
        credentials, host, request_uri, headers, response, content, None
    )
    d.request("GET", request_uri, headers, content, cnonce="33033375ec278a46")
    our_request = "authorization: " + headers["authorization"]
    working_request = (
        'authorization: Digest username="joe", realm="myrealm", '
        'nonce="KBAA=35", uri="/test/digest/"'
        + ', algorithm=MD5, response="de6d4a123b80801d0e94550411b6283f", '
        'qop=auth, nc=00000001, cnonce="33033375ec278a46"'
    )
    assert our_request == working_request


def test_digest_object_with_opaque():
    credentials = ("joe", "password")
    host = None
    request_uri = "/digest/opaque/"
    headers = {}
    response = {
        "www-authenticate": 'Digest realm="myrealm", nonce="30352fd", algorithm=MD5, '
        'qop="auth", opaque="atestopaque"'
    }
    content = ""

    d = httplib2.DigestAuthentication(
        credentials, host, request_uri, headers, response, content, None
    )
    d.request("GET", request_uri, headers, content, cnonce="5ec2")
    our_request = "authorization: " + headers["authorization"]
    working_request = (
        'authorization: Digest username="joe", realm="myrealm", '
        'nonce="30352fd", uri="/digest/opaque/", algorithm=MD5'
        + ', response="a1fab43041f8f3789a447f48018bee48", qop=auth, nc=00000001, '
        'cnonce="5ec2", opaque="atestopaque"'
    )
    assert our_request == working_request


def test_digest_object_stale():
    credentials = ("joe", "password")
    host = None
    request_uri = "/digest/stale/"
    headers = {}
    response = httplib2.Response({})
    response["www-authenticate"] = (
        'Digest realm="myrealm", nonce="bd669f", '
        'algorithm=MD5, qop="auth", stale=true'
    )
    response.status = 401
    content = b""
    d = httplib2.DigestAuthentication(
        credentials, host, request_uri, headers, response, content, None
    )
    # Returns true to force a retry
    assert d.response(response, content)


def test_digest_object_auth_info():
    credentials = ("joe", "password")
    host = None
    request_uri = "/digest/nextnonce/"
    headers = {}
    response = httplib2.Response({})
    response["www-authenticate"] = (
        'Digest realm="myrealm", nonce="barney", '
        'algorithm=MD5, qop="auth", stale=true'
    )
    response["authentication-info"] = 'nextnonce="fred"'
    content = b""
    d = httplib2.DigestAuthentication(
        credentials, host, request_uri, headers, response, content, None
    )
    # Returns true to force a retry
    assert not d.response(response, content)
    assert d.challenge["nonce"] == "fred"
    assert d.challenge["nc"] == 1


def test_wsse_algorithm():
    digest = httplib2._wsse_username_token(
        "d36e316282959a9ed4c89851497a717f", "2003-12-15T14:43:07Z", "taadtaadpstcsm"
    )
    expected = b"quR/EWLAV4xLf9Zqyw4pDmfV9OY="
    assert expected == digest
