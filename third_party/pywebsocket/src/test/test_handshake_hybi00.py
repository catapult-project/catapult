#!/usr/bin/env python
#
# Copyright 2011, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


"""Tests for handshake.hybi00 module."""


import unittest

import set_sys_path  # Update sys.path to locate mod_pywebsocket module.

from mod_pywebsocket.handshake._base import HandshakeException
from mod_pywebsocket.handshake import hybi00 as handshake
from test import mock


_GOOD_REQUEST = (
    80,
    'GET',
    '/demo',
    {
        'Host': 'example.com',
        'Connection': 'Upgrade',
        'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
        'Sec-WebSocket-Protocol': 'sample',
        'Upgrade': 'WebSocket',
        'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
        'Origin': 'http://example.com',
    },
    '^n:ds[4U')

_GOOD_REQUEST_CAPITALIZED_HEADER_VALUES = (
    80,
    'GET',
    '/demo',
    {
        'Host': 'example.com',
        'Connection': 'UPGRADE',
        'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
        'Sec-WebSocket-Protocol': 'sample',
        'Upgrade': 'WEBSOCKET',
        'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
        'Origin': 'http://example.com',
    },
    '^n:ds[4U')

_GOOD_RESPONSE_DEFAULT_PORT = (
    'HTTP/1.1 101 WebSocket Protocol Handshake\r\n'
    'Upgrade: WebSocket\r\n'
    'Connection: Upgrade\r\n'
    'Sec-WebSocket-Location: ws://example.com/demo\r\n'
    'Sec-WebSocket-Origin: http://example.com\r\n'
    'Sec-WebSocket-Protocol: sample\r\n'
    '\r\n'
    '8jKS\'y:G*Co,Wxa-')

_GOOD_RESPONSE_SECURE = (
    'HTTP/1.1 101 WebSocket Protocol Handshake\r\n'
    'Upgrade: WebSocket\r\n'
    'Connection: Upgrade\r\n'
    'Sec-WebSocket-Location: wss://example.com/demo\r\n'
    'Sec-WebSocket-Origin: http://example.com\r\n'
    'Sec-WebSocket-Protocol: sample\r\n'
    '\r\n'
    '8jKS\'y:G*Co,Wxa-')

_GOOD_REQUEST_NONDEFAULT_PORT = (
    8081,
    'GET',
    '/demo',
    {
        'Host': 'example.com:8081',
        'Connection': 'Upgrade',
        'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
        'Sec-WebSocket-Protocol': 'sample',
        'Upgrade': 'WebSocket',
        'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
        'Origin': 'http://example.com',
    },
    '^n:ds[4U')

_GOOD_RESPONSE_NONDEFAULT_PORT = (
    'HTTP/1.1 101 WebSocket Protocol Handshake\r\n'
    'Upgrade: WebSocket\r\n'
    'Connection: Upgrade\r\n'
    'Sec-WebSocket-Location: ws://example.com:8081/demo\r\n'
    'Sec-WebSocket-Origin: http://example.com\r\n'
    'Sec-WebSocket-Protocol: sample\r\n'
    '\r\n'
    '8jKS\'y:G*Co,Wxa-')

_GOOD_RESPONSE_SECURE_NONDEF = (
    'HTTP/1.1 101 WebSocket Protocol Handshake\r\n'
    'Upgrade: WebSocket\r\n'
    'Connection: Upgrade\r\n'
    'Sec-WebSocket-Location: wss://example.com:8081/demo\r\n'
    'Sec-WebSocket-Origin: http://example.com\r\n'
    'Sec-WebSocket-Protocol: sample\r\n'
    '\r\n'
    '8jKS\'y:G*Co,Wxa-')

_GOOD_REQUEST_NO_PROTOCOL = (
    80,
    'GET',
    '/demo',
    {
        'Host': 'example.com',
        'Connection': 'Upgrade',
        'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
        'Upgrade': 'WebSocket',
        'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
        'Origin': 'http://example.com',
    },
    '^n:ds[4U')

_GOOD_RESPONSE_NO_PROTOCOL = (
    'HTTP/1.1 101 WebSocket Protocol Handshake\r\n'
    'Upgrade: WebSocket\r\n'
    'Connection: Upgrade\r\n'
    'Sec-WebSocket-Location: ws://example.com/demo\r\n'
    'Sec-WebSocket-Origin: http://example.com\r\n'
    '\r\n'
    '8jKS\'y:G*Co,Wxa-')

_GOOD_REQUEST_WITH_OPTIONAL_HEADERS = (
    80,
    'GET',
    '/demo',
    {
        'Host': 'example.com',
        'Connection': 'Upgrade',
        'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
        'EmptyValue': '',
        'Sec-WebSocket-Protocol': 'sample',
        'AKey': 'AValue',
        'Upgrade': 'WebSocket',
        'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
        'Origin': 'http://example.com',
    },
    '^n:ds[4U')

# TODO(tyoshino): Include \r \n in key3, challenge response.

_GOOD_REQUEST_WITH_NONPRINTABLE_KEY = (
    80,
    'GET',
    '/demo',
    {
        'Host': 'example.com',
        'Connection': 'Upgrade',
        'Sec-WebSocket-Key2': 'y  R2 48 Q1O4  e|BV3 i5 1  u- 65',
        'Sec-WebSocket-Protocol': 'sample',
        'Upgrade': 'WebSocket',
        'Sec-WebSocket-Key1': '36 7   74 i  92 2\'m 9 0G',
        'Origin': 'http://example.com',
    },
    ''.join(map(chr, [0x01, 0xd1, 0xdd, 0x3b, 0xd1, 0x56, 0x63, 0xff])))

_GOOD_RESPONSE_WITH_NONPRINTABLE_KEY = (
    'HTTP/1.1 101 WebSocket Protocol Handshake\r\n'
    'Upgrade: WebSocket\r\n'
    'Connection: Upgrade\r\n'
    'Sec-WebSocket-Location: ws://example.com/demo\r\n'
    'Sec-WebSocket-Origin: http://example.com\r\n'
    'Sec-WebSocket-Protocol: sample\r\n'
    '\r\n' +
    ''.join(map(chr, [0x0b, 0x99, 0xfa, 0x55, 0xbd, 0x01, 0x23, 0x7b,
                      0x45, 0xa2, 0xf1, 0xd0, 0x87, 0x8a, 0xee, 0xeb])))

_BAD_REQUESTS = (
    (  # HTTP request
        80,
        'GET',
        '/demo',
        {
            'Host': 'www.google.com',
            'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.5;'
                          ' en-US; rv:1.9.1.3) Gecko/20090824 Firefox/3.5.3'
                          ' GTB6 GTBA',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                      '*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Accept-Encoding': 'gzip,deflate',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
            'Keep-Alive': '300',
            'Connection': 'keep-alive',
        }),
    (  # Wrong method
        80,
        'POST',
        '/demo',
        {
            'Host': 'example.com',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
            'Sec-WebSocket-Protocol': 'sample',
            'Upgrade': 'WebSocket',
            'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
            'Origin': 'http://example.com',
        },
        '^n:ds[4U'),
    (  # Missing Upgrade
        80,
        'GET',
        '/demo',
        {
            'Host': 'example.com',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
            'Sec-WebSocket-Protocol': 'sample',
            'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
            'Origin': 'http://example.com',
        },
        '^n:ds[4U'),
    (  # Wrong Upgrade
        80,
        'GET',
        '/demo',
        {
            'Host': 'example.com',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
            'Sec-WebSocket-Protocol': 'sample',
            'Upgrade': 'NonWebSocket',
            'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
            'Origin': 'http://example.com',
        },
        '^n:ds[4U'),
    (  # Empty WebSocket-Protocol
        80,
        'GET',
        '/demo',
        {
            'Host': 'example.com',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
            'Sec-WebSocket-Protocol': '',
            'Upgrade': 'WebSocket',
            'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
            'Origin': 'http://example.com',
        },
        '^n:ds[4U'),
    (  # Wrong port number format
        80,
        'GET',
        '/demo',
        {
            'Host': 'example.com:0x50',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
            'Sec-WebSocket-Protocol': 'sample',
            'Upgrade': 'WebSocket',
            'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
            'Origin': 'http://example.com',
        },
        '^n:ds[4U'),
    (  # Header/connection port mismatch
        8080,
        'GET',
        '/demo',
        {
            'Host': 'example.com',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
            'Sec-WebSocket-Protocol': 'sample',
            'Upgrade': 'WebSocket',
            'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
            'Origin': 'http://example.com',
        },
        '^n:ds[4U'),
    (  # Illegal WebSocket-Protocol
        80,
        'GET',
        '/demo',
        {
            'Host': 'example.com',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key2': '12998 5 Y3 1  .P00',
            'Sec-WebSocket-Protocol': 'illegal\x09protocol',
            'Upgrade': 'WebSocket',
            'Sec-WebSocket-Key1': '4 @1  46546xW%0l 1 5',
            'Origin': 'http://example.com',
        },
        '^n:ds[4U'),
)


def _create_request(request_def):
    data = ''
    if len(request_def) > 4:
        data = request_def[4]
    conn = mock.MockConn(data)
    conn.local_addr = ('0.0.0.0', request_def[0])
    return mock.MockRequest(
        method=request_def[1],
        uri=request_def[2],
        headers_in=request_def[3],
        connection=conn)


def _create_get_memorized_lines(lines):
    """Creates a function that returns the given string."""

    def get_memorized_lines():
        return lines
    return get_memorized_lines


def _create_requests_with_lines(request_lines_set):
    requests = []
    for lines in request_lines_set:
        request = _create_request(_GOOD_REQUEST)
        request.connection.get_memorized_lines = _create_get_memorized_lines(
                lines)
        requests.append(request)
    return requests


class Hybi00HandshakerTest(unittest.TestCase):

    def test_good_request_default_port(self):
        request = _create_request(_GOOD_REQUEST)
        handshaker = handshake.Handshaker(request,
                                          mock.MockDispatcher())
        handshaker.do_handshake()
        self.assertEqual(_GOOD_RESPONSE_DEFAULT_PORT,
                         request.connection.written_data())
        self.assertEqual('/demo', request.ws_resource)
        self.assertEqual('http://example.com', request.ws_origin)
        self.assertEqual('ws://example.com/demo', request.ws_location)
        self.assertEqual('sample', request.ws_protocol)

    def test_good_request_capitalized_header_values(self):
        request = _create_request(_GOOD_REQUEST_CAPITALIZED_HEADER_VALUES)
        handshaker = handshake.Handshaker(request,
                                          mock.MockDispatcher())
        handshaker.do_handshake()
        self.assertEqual(_GOOD_RESPONSE_DEFAULT_PORT,
                         request.connection.written_data())

    def test_good_request_secure_default_port(self):
        request = _create_request(_GOOD_REQUEST)
        request.connection.local_addr = ('0.0.0.0', 443)
        request.is_https_ = True
        handshaker = handshake.Handshaker(request,
                                          mock.MockDispatcher())
        handshaker.do_handshake()
        self.assertEqual(_GOOD_RESPONSE_SECURE,
                         request.connection.written_data())
        self.assertEqual('sample', request.ws_protocol)

    def test_good_request_nondefault_port(self):
        request = _create_request(_GOOD_REQUEST_NONDEFAULT_PORT)
        handshaker = handshake.Handshaker(request,
                                          mock.MockDispatcher())
        handshaker.do_handshake()
        self.assertEqual(_GOOD_RESPONSE_NONDEFAULT_PORT,
                         request.connection.written_data())
        self.assertEqual('sample', request.ws_protocol)

    def test_good_request_secure_non_default_port(self):
        request = _create_request(_GOOD_REQUEST_NONDEFAULT_PORT)
        request.is_https_ = True
        handshaker = handshake.Handshaker(request,
                                          mock.MockDispatcher())
        handshaker.do_handshake()
        self.assertEqual(_GOOD_RESPONSE_SECURE_NONDEF,
                         request.connection.written_data())
        self.assertEqual('sample', request.ws_protocol)

    def test_good_request_default_no_protocol(self):
        request = _create_request(_GOOD_REQUEST_NO_PROTOCOL)
        handshaker = handshake.Handshaker(request,
                                          mock.MockDispatcher())
        handshaker.do_handshake()
        self.assertEqual(_GOOD_RESPONSE_NO_PROTOCOL,
                         request.connection.written_data())
        self.assertEqual(None, request.ws_protocol)

    def test_good_request_optional_headers(self):
        request = _create_request(_GOOD_REQUEST_WITH_OPTIONAL_HEADERS)
        handshaker = handshake.Handshaker(request,
                                          mock.MockDispatcher())
        handshaker.do_handshake()
        self.assertEqual('AValue',
                         request.headers_in['AKey'])
        self.assertEqual('',
                         request.headers_in['EmptyValue'])

    def test_good_request_with_nonprintable_key(self):
        request = _create_request(_GOOD_REQUEST_WITH_NONPRINTABLE_KEY)
        handshaker = handshake.Handshaker(request,
                                          mock.MockDispatcher())
        handshaker.do_handshake()
        self.assertEqual(_GOOD_RESPONSE_WITH_NONPRINTABLE_KEY,
                         request.connection.written_data())
        self.assertEqual('sample', request.ws_protocol)

    def test_bad_requests(self):
        for request in map(_create_request, _BAD_REQUESTS):
            handshaker = handshake.Handshaker(request,
                                              mock.MockDispatcher())
            self.assertRaises(HandshakeException, handshaker.do_handshake)


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
