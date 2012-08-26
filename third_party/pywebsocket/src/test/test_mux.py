#!/usr/bin/env python
#
# Copyright 2012, Google Inc.
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


"""Tests for mux module."""

import Queue
import logging
import optparse
import unittest
import struct
import sys

import set_sys_path  # Update sys.path to locate mod_pywebsocket module.

from mod_pywebsocket import common
from mod_pywebsocket import mux
from mod_pywebsocket._stream_base import ConnectionTerminatedException
from mod_pywebsocket._stream_hybi import Stream
from mod_pywebsocket._stream_hybi import StreamOptions
from mod_pywebsocket._stream_hybi import create_binary_frame
from mod_pywebsocket._stream_hybi import parse_frame

import mock


class _OutgoingChannelData(object):
    def __init__(self):
        self.messages = []
        self.control_messages = []

        self.current_opcode = None
        self.pending_fragments = []


class _MockMuxConnection(mock.MockBlockingConn):
    """Mock class of mod_python connection for mux."""

    def __init__(self):
        mock.MockBlockingConn.__init__(self)
        self._control_blocks = []
        self._channel_data = {}

        self._current_opcode = None
        self._pending_fragments = []

    def write(self, data):
        """Override MockBlockingConn.write."""

        self._current_data = data
        self._position = 0

        def _receive_bytes(length):
            if self._position + length > len(self._current_data):
                raise ConnectionTerminatedException(
                    'Failed to receive %d bytes from encapsulated '
                    'frame' % length)
            data = self._current_data[self._position:self._position+length]
            self._position += length
            return data

        opcode, payload, fin, rsv1, rsv2, rsv3 = (
            parse_frame(_receive_bytes, unmask_receive=False))

        self._pending_fragments.append(payload)

        if self._current_opcode is None:
            if opcode == common.OPCODE_CONTINUATION:
                raise Exception('Sending invalid continuation opcode')
            self._current_opcode = opcode
        else:
            if opcode != common.OPCODE_CONTINUATION:
                raise Exception('Sending invalid opcode %d' % opcode)
        if not fin:
            return

        inner_frame_data = ''.join(self._pending_fragments)
        self._pending_fragments = []
        self._current_opcode = None

        parser = mux._MuxFramePayloadParser(inner_frame_data)
        channel_id = parser.read_channel_id()
        if channel_id == mux._CONTROL_CHANNEL_ID:
            self._control_blocks.append(parser.remaining_data())
            return

        if not channel_id in self._channel_data:
            self._channel_data[channel_id] = _OutgoingChannelData()
        channel_data = self._channel_data[channel_id]

        (inner_fin, inner_rsv1, inner_rsv2, inner_rsv3, inner_opcode,
         inner_payload) = parser.read_inner_frame()
        channel_data.pending_fragments.append(inner_payload)

        if channel_data.current_opcode is None:
            if inner_opcode == common.OPCODE_CONTINUATION:
                raise Exception('Sending invalid continuation opcode')
            channel_data.current_opcode = inner_opcode
        else:
            if inner_opcode != common.OPCODE_CONTINUATION:
                raise Exception('Sending invalid opcode %d' % inner_opcode)
        if not inner_fin:
            return

        message = ''.join(channel_data.pending_fragments)
        channel_data.pending_fragments = []

        if (channel_data.current_opcode == common.OPCODE_TEXT or
            channel_data.current_opcode == common.OPCODE_BINARY):
            channel_data.messages.append(message)
        else:
            channel_data.control_messages.append(
                {'opcode': channel_data.current_opcode,
                 'message': message})
        channel_data.current_opcode = None

    def get_written_control_blocks(self):
        return self._control_blocks

    def get_written_messages(self, channel_id):
        return self._channel_data[channel_id].messages

    def get_written_control_messages(self, channel_id):
        return self._channel_data[channel_id].control_messages


class _ChannelEvent(object):
    """A structure that records channel events."""

    def __init__(self):
        self.messages = []
        self.exception = None
        self.client_initiated_closing = False


class _MuxMockDispatcher(object):
    """Mock class of dispatch.Dispatcher for mux."""

    def __init__(self):
        self.channel_events = {}

    def do_extra_handshake(self, request):
        pass

    def _do_echo(self, request, channel_events):
        while True:
            message = request.ws_stream.receive_message()
            if message == None:
                channel_events.client_initiated_closing = True
                return
            if message == 'Goodbye':
                return
            channel_events.messages.append(message)
            # echo back
            request.ws_stream.send_message(message)

    def _do_ping(self, request, channel_events):
        request.ws_stream.send_ping('Ping!')

    def transfer_data(self, request):
        self.channel_events[request.channel_id] = _ChannelEvent()

        try:
            # Note: more handler will be added.
            if request.uri.endswith('echo'):
                self._do_echo(request,
                              self.channel_events[request.channel_id])
            elif request.uri.endswith('ping'):
                self._do_ping(request,
                              self.channel_events[request.channel_id])
            else:
                raise ValueError('Cannot handle path %r' % request.path)
            if not request.server_terminated:
                request.ws_stream.close_connection()
        except ConnectionTerminatedException, e:
            self.channel_events[request.channel_id].exception = e
        except Exception, e:
            self.channel_events[request.channel_id].exception = e
            raise


def _create_mock_request():
    headers = {'Host': 'server.example.com',
               'Upgrade': 'websocket',
               'Connection': 'Upgrade',
               'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
               'Sec-WebSocket-Version': '13',
               'Origin': 'http://example.com'}
    request = mock.MockRequest(uri='/echo',
                               headers_in=headers,
                               connection=_MockMuxConnection())
    request.ws_stream = Stream(request, options=StreamOptions())
    request.mux = True
    request.mux_extensions = []
    request.mux_quota = 8 * 1024
    return request


def _create_add_channel_request_frame(channel_id, encoding, encoded_handshake):
    if encoding != 0 and encoding != 1:
        raise ValueError('Invalid encoding')
    block = mux._create_control_block_length_value(
               channel_id, mux._MUX_OPCODE_ADD_CHANNEL_REQUEST, encoding,
               encoded_handshake)
    payload = mux._encode_channel_id(mux._CONTROL_CHANNEL_ID) + block
    return create_binary_frame(payload, mask=True)


def _create_logical_frame(channel_id, message, opcode=common.OPCODE_BINARY,
                          mask=True):
    bits = chr(0x80 | opcode)
    payload = mux._encode_channel_id(channel_id) + bits + message
    return create_binary_frame(payload, mask=mask)


def _create_request_header(path='/echo'):
    return (
        'GET %s HTTP/1.1\r\n'
        'Host: server.example.com\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n'
        'Sec-WebSocket-Version: 13\r\n'
        'Origin: http://example.com\r\n'
        '\r\n') % path


class MuxTest(unittest.TestCase):
    """A unittest for mux module."""

    def test_channel_id_decode(self):
        data = '\x00\x01\xbf\xff\xdf\xff\xff\xff\xff\xff\xff'
        parser = mux._MuxFramePayloadParser(data)
        channel_id = parser.read_channel_id()
        self.assertEqual(0, channel_id)
        channel_id = parser.read_channel_id()
        self.assertEqual(1, channel_id)
        channel_id = parser.read_channel_id()
        self.assertEqual(2 ** 14 - 1, channel_id)
        channel_id = parser.read_channel_id()
        self.assertEqual(2 ** 21 - 1, channel_id)
        channel_id = parser.read_channel_id()
        self.assertEqual(2 ** 29 - 1, channel_id)
        self.assertEqual(len(data), parser._read_position)

    def test_channel_id_encode(self):
        encoded = mux._encode_channel_id(0)
        self.assertEqual('\x00', encoded)
        encoded = mux._encode_channel_id(2 ** 14 - 1)
        self.assertEqual('\xbf\xff', encoded)
        encoded = mux._encode_channel_id(2 ** 14)
        self.assertEqual('\xc0@\x00', encoded)
        encoded = mux._encode_channel_id(2 ** 21 - 1)
        self.assertEqual('\xdf\xff\xff', encoded)
        encoded = mux._encode_channel_id(2 ** 21)
        self.assertEqual('\xe0 \x00\x00', encoded)
        encoded = mux._encode_channel_id(2 ** 29 - 1)
        self.assertEqual('\xff\xff\xff\xff', encoded)
        # channel_id is too large
        self.assertRaises(ValueError,
                          mux._encode_channel_id,
                          2 ** 29)

    def test_create_control_block_length_value(self):
        data = 'Hello, world!'
        block = mux._create_control_block_length_value(
            channel_id=1, opcode=mux._MUX_OPCODE_ADD_CHANNEL_REQUEST,
            flags=0x7, value=data)
        expected = '\x1c\x01\x0dHello, world!'
        self.assertEqual(expected, block)

        data = 'a' * (2 ** 8)
        block = mux._create_control_block_length_value(
            channel_id=2, opcode=mux._MUX_OPCODE_ADD_CHANNEL_RESPONSE,
            flags=0x0, value=data)
        expected = '\x21\x02\x01\x00' + data
        self.assertEqual(expected, block)

        data = 'b' * (2 ** 16)
        block = mux._create_control_block_length_value(
            channel_id=3, opcode=mux._MUX_OPCODE_DROP_CHANNEL,
            flags=0x0, value=data)
        expected = '\x62\x03\x01\x00\x00' + data
        self.assertEqual(expected, block)

    def test_read_control_blocks(self):
        data = ('\x00\x01\00'
                '\x61\x02\x01\x00%s'
                '\x0a\x03\x01\x00\x00%s'
                '\x63\x04\x01\x00\x00\x00%s') % (
            'a' * 0x0100, 'b' * 0x010000, 'c' * 0x01000000)
        parser = mux._MuxFramePayloadParser(data)
        blocks = list(parser.read_control_blocks())
        self.assertEqual(4, len(blocks))

        self.assertEqual(mux._MUX_OPCODE_ADD_CHANNEL_REQUEST, blocks[0].opcode)
        self.assertEqual(0, blocks[0].encoding)
        self.assertEqual(0, len(blocks[0].encoded_handshake))

        self.assertEqual(mux._MUX_OPCODE_DROP_CHANNEL, blocks[1].opcode)
        self.assertEqual(0, blocks[1].mux_error)
        self.assertEqual(0x0100, len(blocks[1].reason))

        self.assertEqual(mux._MUX_OPCODE_ADD_CHANNEL_REQUEST, blocks[2].opcode)
        self.assertEqual(2, blocks[2].encoding)
        self.assertEqual(0x010000, len(blocks[2].encoded_handshake))

        self.assertEqual(mux._MUX_OPCODE_DROP_CHANNEL, blocks[3].opcode)
        self.assertEqual(0, blocks[3].mux_error)
        self.assertEqual(0x01000000, len(blocks[3].reason))

        self.assertEqual(len(data), parser._read_position)

    def test_create_add_channel_response(self):
        data = mux._create_add_channel_response(channel_id=1,
                                                encoded_handshake='FooBar',
                                                encoding=0,
                                                rejected=False)
        self.assertEqual('\x82\x0a\x00\x20\x01\x06FooBar', data)

        data = mux._create_add_channel_response(channel_id=2,
                                                encoded_handshake='Hello',
                                                encoding=1,
                                                rejected=True)
        self.assertEqual('\x82\x09\x00\x34\x02\x05Hello', data)

    def test_drop_channel(self):
        data = mux._create_drop_channel(channel_id=1,
                                        reason='',
                                        mux_error=False)
        self.assertEqual('\x82\x04\x00\x60\x01\x00', data)

        data = mux._create_drop_channel(channel_id=1,
                                        reason='error',
                                        mux_error=True)
        self.assertEqual('\x82\x09\x00\x70\x01\x05error', data)

        # reason must be empty if mux_error is False.
        self.assertRaises(ValueError,
                          mux._create_drop_channel,
                          1, 'FooBar', False)

    def test_parse_request_text(self):
        request_text = _create_request_header()
        command, path, version, headers = mux._parse_request_text(request_text)
        self.assertEqual('GET', command)
        self.assertEqual('/echo', path)
        self.assertEqual('HTTP/1.1', version)
        self.assertEqual(6, len(headers))
        self.assertEqual('server.example.com', headers['Host'])
        self.assertEqual('websocket', headers['Upgrade'])
        self.assertEqual('Upgrade', headers['Connection'])
        self.assertEqual('dGhlIHNhbXBsZSBub25jZQ==',
                         headers['Sec-WebSocket-Key'])
        self.assertEqual('13', headers['Sec-WebSocket-Version'])
        self.assertEqual('http://example.com', headers['Origin'])


class MuxHandlerTest(unittest.TestCase):

    def test_add_channel(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS,
                                      mux._INITIAL_QUOTA_FOR_CLIENT)

        encoded_handshake = _create_request_header(path='/echo')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        flow_control = mux._create_flow_control(channel_id=2,
                                                replenished_quota=5,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        encoded_handshake = _create_request_header(path='/echo')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=3, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        flow_control = mux._create_flow_control(channel_id=3,
                                                replenished_quota=5,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=2, message='Hello'))
        request.connection.put_bytes(
            _create_logical_frame(channel_id=3, message='World'))
        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))
        request.connection.put_bytes(
            _create_logical_frame(channel_id=2, message='Goodbye'))
        request.connection.put_bytes(
            _create_logical_frame(channel_id=3, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)

        self.assertEqual([], dispatcher.channel_events[1].messages)
        self.assertEqual(['Hello'], dispatcher.channel_events[2].messages)
        self.assertEqual(['World'], dispatcher.channel_events[3].messages)
        # Channel 2
        messages = request.connection.get_written_messages(2)
        self.assertEqual(1, len(messages))
        self.assertEqual('Hello', messages[0])
        # Channel 3
        messages = request.connection.get_written_messages(3)
        self.assertEqual(1, len(messages))
        self.assertEqual('World', messages[0])
        control_blocks = request.connection.get_written_control_blocks()
        # There should be 8 control blocks:
        #   - 1 NewChannelSlot
        #   - 2 AddChannelResponses for channel id 2 and 3
        #   - 6 FlowControls for channel id 1 (initialize), 'Hello', 'World',
        #     and 3 'Goodbye's
        self.assertEqual(9, len(control_blocks))

    def test_add_channel_incomplete_handshake(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS,
                                      mux._INITIAL_QUOTA_FOR_CLIENT)

        incomplete_encoded_handshake = 'GET /echo HTTP/1.1'
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=incomplete_encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)

        self.assertTrue(1 in dispatcher.channel_events)
        self.assertTrue(not 2 in dispatcher.channel_events)

    def test_add_channel_invalid_version_handshake(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS,
                                      mux._INITIAL_QUOTA_FOR_CLIENT)

        encoded_handshake = (
            'GET /echo HTTP/1.1\r\n'
            'Host: example.com\r\n'
            'Connection: Upgrade\r\n'
            'Sec-WebSocket-Key2: 12998 5 Y3 1  .P00\r\n'
            'Sec-WebSocket-Protocol: sample\r\n'
            'Upgrade: WebSocket\r\n'
            'Sec-WebSocket-Key1: 4 @1  46546xW%0l 1 5\r\n'
            'Origin: http://example.com\r\n'
            '\r\n'
            '^n:ds[4U')

        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)

        self.assertTrue(1 in dispatcher.channel_events)
        self.assertTrue(not 2 in dispatcher.channel_events)

    def test_receive_drop_channel(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS,
                                      mux._INITIAL_QUOTA_FOR_CLIENT)

        encoded_handshake = _create_request_header(path='/echo')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        drop_channel = mux._create_drop_channel(channel_id=2,
                                                outer_frame_mask=True)
        request.connection.put_bytes(drop_channel)

        # Terminate implicitly opened channel.
        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)

        exception = dispatcher.channel_events[2].exception
        self.assertTrue(exception.__class__ == ConnectionTerminatedException)

    def test_receive_ping_frame(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS,
                                      mux._INITIAL_QUOTA_FOR_CLIENT)

        encoded_handshake = _create_request_header(path='/echo')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        flow_control = mux._create_flow_control(channel_id=2,
                                                replenished_quota=12,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        ping_frame = _create_logical_frame(channel_id=2,
                                           message='Hello World!',
                                           opcode=common.OPCODE_PING)
        request.connection.put_bytes(ping_frame)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))
        request.connection.put_bytes(
            _create_logical_frame(channel_id=2, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)

        messages = request.connection.get_written_control_messages(2)
        self.assertEqual(common.OPCODE_PONG, messages[0]['opcode'])
        self.assertEqual('Hello World!', messages[0]['message'])

    def test_send_ping(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS,
                                      mux._INITIAL_QUOTA_FOR_CLIENT)

        encoded_handshake = _create_request_header(path='/ping')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        flow_control = mux._create_flow_control(channel_id=2,
                                                replenished_quota=5,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)

        messages = request.connection.get_written_control_messages(2)
        self.assertEqual(common.OPCODE_PING, messages[0]['opcode'])
        self.assertEqual('Ping!', messages[0]['message'])

    def test_two_flow_control(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS,
                                      mux._INITIAL_QUOTA_FOR_CLIENT)

        encoded_handshake = _create_request_header(path='/echo')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        # Replenish 5 bytes.
        flow_control = mux._create_flow_control(channel_id=2,
                                                replenished_quota=5,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        # Send 10 bytes. The server will try echo back 10 bytes.
        request.connection.put_bytes(
            _create_logical_frame(channel_id=2, message='HelloWorld'))

        # Replenish 5 bytes again.
        flow_control = mux._create_flow_control(channel_id=2,
                                                replenished_quota=5,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))
        request.connection.put_bytes(
            _create_logical_frame(channel_id=2, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)

        messages = request.connection.get_written_messages(2)
        self.assertEqual(['HelloWorld'], messages)

    def test_no_send_quota_on_server(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS,
                                      mux._INITIAL_QUOTA_FOR_CLIENT)

        encoded_handshake = _create_request_header(path='/echo')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=2, message='HelloWorld'))

        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))

        mux_handler.wait_until_done(timeout=1)

        # No message should be sent on channel 2.
        self.assertRaises(KeyError,
                          request.connection.get_written_messages,
                          2)

    def test_quota_violation_by_client(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS, 0)

        encoded_handshake = _create_request_header(path='/echo')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=2, message='HelloWorld'))

        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)
        control_blocks = request.connection.get_written_control_blocks()
        # The first block is FlowControl for channel id 1.
        # The next two blocks are NewChannelSlot and AddChannelResponse.
        # The 4th block or the last block should be DropChannels for channel 2.
        # (The order can be mixed up)
        # The remaining block should be FlowControl for 'Goodbye'.
        self.assertEqual(5, len(control_blocks))
        expected_opcode_and_flag = ((mux._MUX_OPCODE_DROP_CHANNEL << 5) |
                                    (1 << 4))
        self.assertTrue((expected_opcode_and_flag ==
                        (ord(control_blocks[3][0]) & 0xf0)) or
                        (expected_opcode_and_flag ==
                        (ord(control_blocks[4][0]) & 0xf0)))

    def test_fragmented_control_message(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(mux._INITIAL_NUMBER_OF_CHANNEL_SLOTS,
                                      mux._INITIAL_QUOTA_FOR_CLIENT)

        encoded_handshake = _create_request_header(path='/ping')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)

        # Replenish total 5 bytes in 3 FlowControls.
        flow_control = mux._create_flow_control(channel_id=2,
                                                replenished_quota=1,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        flow_control = mux._create_flow_control(channel_id=2,
                                                replenished_quota=2,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        flow_control = mux._create_flow_control(channel_id=2,
                                                replenished_quota=2,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)

        messages = request.connection.get_written_control_messages(2)
        self.assertEqual(common.OPCODE_PING, messages[0]['opcode'])
        self.assertEqual('Ping!', messages[0]['message'])

    def test_channel_slot_violation_by_client(self):
        request = _create_mock_request()
        dispatcher = _MuxMockDispatcher()
        mux_handler = mux._MuxHandler(request, dispatcher)
        mux_handler.start()
        mux_handler.add_channel_slots(slots=1,
                                      send_quota=mux._INITIAL_QUOTA_FOR_CLIENT)

        encoded_handshake = _create_request_header(path='/echo')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=2, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)
        flow_control = mux._create_flow_control(channel_id=2,
                                                replenished_quota=10,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=2, message='Hello'))

        # This request should be rejected.
        encoded_handshake = _create_request_header(path='/echo')
        add_channel_request = _create_add_channel_request_frame(
            channel_id=3, encoding=0,
            encoded_handshake=encoded_handshake)
        request.connection.put_bytes(add_channel_request)
        flow_control = mux._create_flow_control(channel_id=3,
                                                replenished_quota=5,
                                                outer_frame_mask=True)
        request.connection.put_bytes(flow_control)

        request.connection.put_bytes(
            _create_logical_frame(channel_id=3, message='Hello'))

        request.connection.put_bytes(
            _create_logical_frame(channel_id=1, message='Goodbye'))
        request.connection.put_bytes(
            _create_logical_frame(channel_id=2, message='Goodbye'))

        mux_handler.wait_until_done(timeout=2)

        self.assertEqual(['Hello'], dispatcher.channel_events[2].messages)
        self.assertFalse(dispatcher.channel_events.has_key(3))


if __name__ == '__main__':
    unittest.main()


# vi:sts=4 sw=4 et
