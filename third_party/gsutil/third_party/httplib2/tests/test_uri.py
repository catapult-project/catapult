import httplib2


def test_from_std66():
    cases = (
        ('http://example.com',
            ('http', 'example.com', '', None, None)),
        ('https://example.com',
            ('https', 'example.com', '', None, None)),
        ('https://example.com:8080',
            ('https', 'example.com:8080', '', None, None)),
        ('http://example.com/',
            ('http', 'example.com', '/', None, None)),
        ('http://example.com/path',
            ('http', 'example.com', '/path', None, None)),
        ('http://example.com/path?a=1&b=2',
            ('http', 'example.com', '/path', 'a=1&b=2', None)),
        ('http://example.com/path?a=1&b=2#fred',
            ('http', 'example.com', '/path', 'a=1&b=2', 'fred')),
        ('http://example.com/path?a=1&b=2#fred',
            ('http', 'example.com', '/path', 'a=1&b=2', 'fred')),
    )
    for a, b in cases:
        assert httplib2.parse_uri(a) == b


def test_norm():
    cases = (
        ('http://example.org',
            'http://example.org/'),
        ('http://EXAMple.org',
            'http://example.org/'),
        ('http://EXAMple.org?=b',
            'http://example.org/?=b'),
        ('http://EXAMple.org/mypath?a=b',
            'http://example.org/mypath?a=b'),
        ('http://localhost:80',
            'http://localhost:80/'),
    )
    for a, b in cases:
        assert httplib2.urlnorm(a)[-1] == b

    assert httplib2.urlnorm('http://localhost:80/') == httplib2.urlnorm('HTTP://LOCALHOST:80')

    try:
        httplib2.urlnorm('/')
        assert False, 'Non-absolute URIs should raise an exception'
    except httplib2.RelativeURIError:
        pass


def test_safename():
    cases = (
        ('http://example.org/fred/?a=b',
            'example.org,fred,a=b,58489f63a7a83c3b7794a6a398ee8b1f'),
        ('http://example.org/fred?/a=b',
            'example.org,fred,a=b,8c5946d56fec453071f43329ff0be46b'),
        ('http://www.example.org/fred?/a=b',
            'www.example.org,fred,a=b,499c44b8d844a011b67ea2c015116968'),
        ('https://www.example.org/fred?/a=b',
            'www.example.org,fred,a=b,692e843a333484ce0095b070497ab45d'),
        (httplib2.urlnorm('http://WWW')[-1],
            httplib2.safename(httplib2.urlnorm('http://www')[-1])),
        (u'http://\u2304.org/fred/?a=b',
            'xn--http,-4y1d.org,fred,a=b,579924c35db315e5a32e3d9963388193'),
    )
    for a, b in cases:
        assert httplib2.safename(a) == b

    assert httplib2.safename('http://www') != httplib2.safename('https://www')

    # Test the max length limits
    uri = 'http://' + ('w' * 200) + '.org'
    uri2 = 'http://' + ('w' * 201) + '.org'
    assert httplib2.safename(uri) != httplib2.safename(uri2)
    # Max length should be 200 + 1 (',') + 32
    assert len(httplib2.safename(uri2)) == 233
    assert len(httplib2.safename(uri)) == 233
