#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Tests for protorpc.service_handlers."""

__author__ = 'rafek@google.com (Rafe Kaplan)'


import cgi
import cStringIO
import os
import re
import sys
import unittest
import urllib

from protorpc import messages
from protorpc import protobuf
from protorpc import protojson
from protorpc import protourlencode
from protorpc import message_types
from protorpc import registry
from protorpc import remote
from protorpc import test_util
from protorpc import util
from protorpc import webapp_test_util
from protorpc.webapp import forms
from protorpc.webapp import service_handlers
from protorpc.webapp.google_imports import webapp

import mox

package = 'test_package'


class ModuleInterfaceTest(test_util.ModuleInterfaceTest,
                          test_util.TestCase):

  MODULE = service_handlers


class Enum1(messages.Enum):
  """A test enum class."""

  VAL1 = 1
  VAL2 = 2
  VAL3 = 3


class Request1(messages.Message):
  """A test request message type."""

  integer_field = messages.IntegerField(1)
  string_field = messages.StringField(2)
  enum_field = messages.EnumField(Enum1, 3)


class Response1(messages.Message):
  """A test response message type."""

  integer_field = messages.IntegerField(1)
  string_field = messages.StringField(2)
  enum_field = messages.EnumField(Enum1, 3)


class SuperMessage(messages.Message):
  """A test message with a nested message field."""

  sub_message = messages.MessageField(Request1, 1)
  sub_messages = messages.MessageField(Request1, 2, repeated=True)


class SuperSuperMessage(messages.Message):
  """A test message with two levels of nested."""

  sub_message = messages.MessageField(SuperMessage, 1)
  sub_messages = messages.MessageField(Request1, 2, repeated=True)


class RepeatedMessage(messages.Message):
  """A test message with a repeated field."""

  ints = messages.IntegerField(1, repeated=True)
  strings = messages.StringField(2, repeated=True)
  enums = messages.EnumField(Enum1, 3, repeated=True)


class Service(object):
  """A simple service that takes a Request1 and returns Request2."""

  @remote.method(Request1, Response1)
  def method1(self, request):
    response = Response1()
    if hasattr(request, 'integer_field'):
      response.integer_field = request.integer_field
    if hasattr(request, 'string_field'):
      response.string_field = request.string_field
    if hasattr(request, 'enum_field'):
      response.enum_field = request.enum_field
    return response

  @remote.method(RepeatedMessage, RepeatedMessage)
  def repeated_method(self, request):
    response = RepeatedMessage()
    if hasattr(request, 'ints'):
      response = request.ints
    return response

  def not_remote(self):
    pass


def VerifyResponse(test,
                   response,
                   expected_status,
                   expected_status_message,
                   expected_content,
                   expected_content_type='application/x-www-form-urlencoded'):
  def write(content):
    if expected_content == '':
      test.assertEquals(util.pad_string(''), content)
    else:
      test.assertNotEquals(-1, content.find(expected_content),
                           'Expected to find:\n%s\n\nActual content: \n%s' % (
                             expected_content, content))

  def start_response(response, headers):
    status, message = response.split(' ', 1)
    test.assertEquals(expected_status, status)
    test.assertEquals(expected_status_message, message)
    for name, value in headers:
      if name.lower() == 'content-type':
        test.assertEquals(expected_content_type, value)
    for name, value in headers:
      if name.lower() == 'x-content-type-options':
        test.assertEquals('nosniff', value)
      elif name.lower() == 'content-type':
        test.assertFalse(value.lower().startswith('text/html'))
    return write

  response.wsgi_write(start_response)


class ServiceHandlerFactoryTest(test_util.TestCase):
  """Tests for the service handler factory."""

  def testAllRequestMappers(self):
    """Test all_request_mappers method."""
    configuration = service_handlers.ServiceHandlerFactory(Service)
    mapper1 = service_handlers.RPCMapper(['whatever'], 'whatever', None)
    mapper2 = service_handlers.RPCMapper(['whatever'], 'whatever', None)

    configuration.add_request_mapper(mapper1)
    self.assertEquals([mapper1], list(configuration.all_request_mappers()))

    configuration.add_request_mapper(mapper2)
    self.assertEquals([mapper1, mapper2],
                      list(configuration.all_request_mappers()))

  def testServiceFactory(self):
    """Test that service_factory attribute is set."""
    handler_factory = service_handlers.ServiceHandlerFactory(Service)
    self.assertEquals(Service, handler_factory.service_factory)

  def testFactoryMethod(self):
    """Test that factory creates correct instance of class."""
    factory = service_handlers.ServiceHandlerFactory(Service)
    handler = factory()

    self.assertTrue(isinstance(handler, service_handlers.ServiceHandler))
    self.assertTrue(isinstance(handler.service, Service))

  def testMapping(self):
    """Test the mapping method."""
    factory = service_handlers.ServiceHandlerFactory(Service)
    path, mapped_factory = factory.mapping('/my_service')

    self.assertEquals(r'(/my_service)' + service_handlers._METHOD_PATTERN, path)
    self.assertEquals(id(factory), id(mapped_factory))
    match = re.match(path, '/my_service.my_method')
    self.assertEquals('/my_service', match.group(1))
    self.assertEquals('my_method', match.group(2))

    path, mapped_factory = factory.mapping('/my_service/nested')
    self.assertEquals('(/my_service/nested)' +
                      service_handlers._METHOD_PATTERN, path)
    match = re.match(path, '/my_service/nested.my_method')
    self.assertEquals('/my_service/nested', match.group(1))
    self.assertEquals('my_method', match.group(2))

  def testRegexMapping(self):
    """Test the mapping method using a regex."""
    factory = service_handlers.ServiceHandlerFactory(Service)
    path, mapped_factory = factory.mapping('.*/my_service')

    self.assertEquals(r'(.*/my_service)' + service_handlers._METHOD_PATTERN, path)
    self.assertEquals(id(factory), id(mapped_factory))
    match = re.match(path, '/whatever_preceeds/my_service.my_method')
    self.assertEquals('/whatever_preceeds/my_service', match.group(1))
    self.assertEquals('my_method', match.group(2))
    match = re.match(path, '/something_else/my_service.my_other_method')
    self.assertEquals('/something_else/my_service', match.group(1))
    self.assertEquals('my_other_method', match.group(2))

  def testMapping_BadPath(self):
    """Test bad parameterse to the mapping method."""
    factory = service_handlers.ServiceHandlerFactory(Service)
    self.assertRaises(ValueError, factory.mapping, '/my_service/')

  def testDefault(self):
    """Test the default factory convenience method."""
    handler_factory = service_handlers.ServiceHandlerFactory.default(
        Service,
        parameter_prefix='my_prefix.')

    self.assertEquals(Service, handler_factory.service_factory)

    mappers = handler_factory.all_request_mappers()

    # Verify Protobuf encoded mapper.
    protobuf_mapper = next(mappers)
    self.assertTrue(isinstance(protobuf_mapper,
                               service_handlers.ProtobufRPCMapper))

    # Verify JSON encoded mapper.
    json_mapper = next(mappers)
    self.assertTrue(isinstance(json_mapper,
                               service_handlers.JSONRPCMapper))

    # Should have no more mappers.
    self.assertRaises(StopIteration, mappers.next)


class ServiceHandlerTest(webapp_test_util.RequestHandlerTestBase):
  """Test the ServiceHandler class."""

  def setUp(self):
    self.mox = mox.Mox()
    self.service_factory = Service
    self.remote_host = 'remote.host.com'
    self.server_host = 'server.host.com'
    self.ResetRequestHandler()

    self.request = Request1()
    self.request.integer_field = 1
    self.request.string_field = 'a'
    self.request.enum_field = Enum1.VAL1

  def ResetRequestHandler(self):
    super(ServiceHandlerTest, self).setUp()

  def CreateService(self):
    return self.service_factory()

  def CreateRequestHandler(self):
    self.rpc_mapper1 = self.mox.CreateMock(service_handlers.RPCMapper)
    self.rpc_mapper1.http_methods = set(['POST'])
    self.rpc_mapper1.content_types = set(['application/x-www-form-urlencoded'])
    self.rpc_mapper1.default_content_type = 'application/x-www-form-urlencoded'
    self.rpc_mapper2 = self.mox.CreateMock(service_handlers.RPCMapper)
    self.rpc_mapper2.http_methods = set(['GET'])
    self.rpc_mapper2.content_types = set(['application/json'])
    self.rpc_mapper2.default_content_type = 'application/json'
    self.factory = service_handlers.ServiceHandlerFactory(
        self.CreateService)
    self.factory.add_request_mapper(self.rpc_mapper1)
    self.factory.add_request_mapper(self.rpc_mapper2)
    return self.factory()

  def GetEnvironment(self):
    """Create handler to test."""
    environ = super(ServiceHandlerTest, self).GetEnvironment()
    if self.remote_host:
      environ['REMOTE_HOST'] = self.remote_host
    if self.server_host:
      environ['SERVER_HOST'] = self.server_host
    return environ

  def VerifyResponse(self, *args, **kwargs):
    VerifyResponse(self,
                   self.response,
                   *args, **kwargs)

  def ExpectRpcError(self, mapper, state, error_message, error_name=None):
    mapper.build_response(self.handler,
                          remote.RpcStatus(state=state,
                                           error_message=error_message,
                                           error_name=error_name))

  def testRedirect(self):
    """Test that redirection is disabled."""
    self.assertRaises(NotImplementedError, self.handler.redirect, '/')

  def testFirstMapper(self):
    """Make sure service attribute works when matches first RPCMapper."""
    self.rpc_mapper1.build_request(
        self.handler, Request1).AndReturn(self.request)

    def build_response(handler, response):
      output = '%s %s %s' % (response.integer_field,
                             response.string_field,
                             response.enum_field)
      handler.response.headers['content-type'] = (
        'application/x-www-form-urlencoded')
      handler.response.out.write(output)
    self.rpc_mapper1.build_response(
        self.handler, mox.IsA(Response1)).WithSideEffects(build_response)

    self.mox.ReplayAll()

    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('200', 'OK', '1 a VAL1')

    self.mox.VerifyAll()

  def testSecondMapper(self):
    """Make sure service attribute works when matches first RPCMapper.

    Demonstrates the multiplicity of the RPCMapper configuration.
    """
    self.rpc_mapper2.build_request(
        self.handler, Request1).AndReturn(self.request)

    def build_response(handler, response):
      output = '%s %s %s' % (response.integer_field,
                             response.string_field,
                             response.enum_field)
      handler.response.headers['content-type'] = (
        'application/x-www-form-urlencoded')
      handler.response.out.write(output)
    self.rpc_mapper2.build_response(
        self.handler, mox.IsA(Response1)).WithSideEffects(build_response)

    self.mox.ReplayAll()

    self.handler.request.headers['Content-Type'] = 'application/json'
    self.handler.handle('GET', '/my_service', 'method1')

    self.VerifyResponse('200', 'OK', '1 a VAL1')

    self.mox.VerifyAll()

  def testCaseInsensitiveContentType(self):
    """Ensure that matching content-type is case insensitive."""
    request = Request1()
    request.integer_field = 1
    request.string_field = 'a'
    request.enum_field = Enum1.VAL1
    self.rpc_mapper1.build_request(self.handler,
                                   Request1).AndReturn(self.request)

    def build_response(handler, response):
      output = '%s %s %s' % (response.integer_field,
                             response.string_field,
                             response.enum_field)
      handler.response.out.write(output)
      handler.response.headers['content-type'] = 'text/plain'
    self.rpc_mapper1.build_response(
        self.handler, mox.IsA(Response1)).WithSideEffects(build_response)

    self.mox.ReplayAll()

    self.handler.request.headers['Content-Type'] = ('ApPlIcAtIoN/'
                                                    'X-wWw-FoRm-UrLeNcOdEd')

    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('200', 'OK', '1 a VAL1', 'text/plain')

    self.mox.VerifyAll()

  def testContentTypeWithParameters(self):
    """Test that content types have parameters parsed out."""
    request = Request1()
    request.integer_field = 1
    request.string_field = 'a'
    request.enum_field = Enum1.VAL1
    self.rpc_mapper1.build_request(self.handler,
                                   Request1).AndReturn(self.request)

    def build_response(handler, response):
      output = '%s %s %s' % (response.integer_field,
                             response.string_field,
                             response.enum_field)
      handler.response.headers['content-type'] = (
        'application/x-www-form-urlencoded')
      handler.response.out.write(output)
    self.rpc_mapper1.build_response(
        self.handler, mox.IsA(Response1)).WithSideEffects(build_response)

    self.mox.ReplayAll()

    self.handler.request.headers['Content-Type'] = ('application/'
                                                    'x-www-form-urlencoded' +
                                                    '; a=b; c=d')

    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('200', 'OK', '1 a VAL1')

    self.mox.VerifyAll()

  def testContentFromHeaderOnly(self):
    """Test getting content-type from HTTP_CONTENT_TYPE directly.

    Some bad web server implementations might decide not to set CONTENT_TYPE for
    POST requests where there is an empty body.  In these cases, need to get
    content-type directly from webob environ key HTTP_CONTENT_TYPE.
    """
    request = Request1()
    request.integer_field = 1
    request.string_field = 'a'
    request.enum_field = Enum1.VAL1
    self.rpc_mapper1.build_request(self.handler,
                                   Request1).AndReturn(self.request)

    def build_response(handler, response):
      output = '%s %s %s' % (response.integer_field,
                             response.string_field,
                             response.enum_field)
      handler.response.headers['Content-Type'] = (
        'application/x-www-form-urlencoded')
      handler.response.out.write(output)
    self.rpc_mapper1.build_response(
        self.handler, mox.IsA(Response1)).WithSideEffects(build_response)

    self.mox.ReplayAll()

    self.handler.request.headers['Content-Type'] = None
    self.handler.request.environ['HTTP_CONTENT_TYPE'] = (
      'application/x-www-form-urlencoded')

    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('200', 'OK', '1 a VAL1',
                        'application/x-www-form-urlencoded')

    self.mox.VerifyAll()

  def testRequestState(self):
    """Make sure request state is passed in to handler that supports it."""
    class ServiceWithState(object):

      initialize_request_state = self.mox.CreateMockAnything()

      @remote.method(Request1, Response1)
      def method1(self, request):
        return Response1()

    self.service_factory = ServiceWithState

    # Reset handler with new service type.
    self.ResetRequestHandler()

    self.rpc_mapper1.build_request(
        self.handler, Request1).AndReturn(Request1())

    def build_response(handler, response):
      handler.response.headers['Content-Type'] = (
        'application/x-www-form-urlencoded')
      handler.response.out.write('whatever')
    self.rpc_mapper1.build_response(
        self.handler, mox.IsA(Response1)).WithSideEffects(build_response)

    def verify_state(state):
      return (
        'remote.host.com' ==  state.remote_host and
        '127.0.0.1' == state.remote_address and
        'server.host.com' == state.server_host and
        8080 == state.server_port and
        'POST' == state.http_method and
        '/my_service' == state.service_path and
        'application/x-www-form-urlencoded' == state.headers['content-type'] and
        'dev_appserver_login="test:test@example.com:True"' ==
        state.headers['cookie'])
    ServiceWithState.initialize_request_state(mox.Func(verify_state))

    self.mox.ReplayAll()

    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('200', 'OK', 'whatever')

    self.mox.VerifyAll()

  def testRequestState_MissingHosts(self):
    """Make sure missing state environment values are handled gracefully."""
    class ServiceWithState(object):

      initialize_request_state = self.mox.CreateMockAnything()

      @remote.method(Request1, Response1)
      def method1(self, request):
        return Response1()

    self.service_factory = ServiceWithState
    self.remote_host = None
    self.server_host = None

    # Reset handler with new service type.
    self.ResetRequestHandler()

    self.rpc_mapper1.build_request(
        self.handler, Request1).AndReturn(Request1())

    def build_response(handler, response):
      handler.response.headers['Content-Type'] = (
        'application/x-www-form-urlencoded')
      handler.response.out.write('whatever')
    self.rpc_mapper1.build_response(
        self.handler, mox.IsA(Response1)).WithSideEffects(build_response)

    def verify_state(state):
      return (None is state.remote_host and
              '127.0.0.1' == state.remote_address and
              None is state.server_host and
              8080 == state.server_port)
    ServiceWithState.initialize_request_state(mox.Func(verify_state))

    self.mox.ReplayAll()

    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('200', 'OK', 'whatever')

    self.mox.VerifyAll()

  def testNoMatch_UnknownHTTPMethod(self):
    """Test what happens when no RPCMapper matches."""
    self.mox.ReplayAll()

    self.handler.handle('UNKNOWN', '/my_service', 'does_not_matter')

    self.VerifyResponse('405',
                        'Unsupported HTTP method: UNKNOWN',
                        'Method Not Allowed',
                        'text/plain; charset=utf-8')

    self.mox.VerifyAll()

  def testNoMatch_GetNotSupported(self):
    """Test what happens when GET is not supported."""
    self.mox.ReplayAll()

    self.handler.handle('GET', '/my_service', 'method1')

    self.VerifyResponse('405',
                        'Method Not Allowed',
                        '/my_service.method1 is a ProtoRPC method.\n\n'
                        'Service %s.Service\n\n'
                        'More about ProtoRPC: '
                        'http://code.google.com/p/google-protorpc' %
                        (__name__,),
                        'text/plain; charset=utf-8')

    self.mox.VerifyAll()

  def testNoMatch_UnknownContentType(self):
    """Test what happens when no RPCMapper matches."""
    self.mox.ReplayAll()

    self.handler.request.headers['Content-Type'] = 'image/png'
    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('415',
                        'Unsupported content-type: image/png',
                        'Unsupported Media Type',
                        'text/plain; charset=utf-8')

    self.mox.VerifyAll()

  def testNoMatch_NoContentType(self):
    """Test what happens when no RPCMapper matches.."""
    self.mox.ReplayAll()

    self.handler.request.environ.pop('HTTP_CONTENT_TYPE', None)
    self.handler.request.headers.pop('Content-Type', None)
    self.handler.handle('/my_service', 'POST', 'method1')

    self.VerifyResponse('400', 'Invalid RPC request: missing content-type',
                        'Bad Request',
                        'text/plain; charset=utf-8')

    self.mox.VerifyAll()

  def testNoSuchMethod(self):
    """When service method not found."""
    self.ExpectRpcError(self.rpc_mapper1,
                        remote.RpcState.METHOD_NOT_FOUND_ERROR,
                        'Unrecognized RPC method: no_such_method')

    self.mox.ReplayAll()

    self.handler.handle('POST', '/my_service', 'no_such_method')

    self.VerifyResponse('400', 'Unrecognized RPC method: no_such_method', '')

    self.mox.VerifyAll()

  def testNoSuchRemoteMethod(self):
    """When service method exists but is not remote."""
    self.ExpectRpcError(self.rpc_mapper1,
                        remote.RpcState.METHOD_NOT_FOUND_ERROR,
                        'Unrecognized RPC method: not_remote')

    self.mox.ReplayAll()

    self.handler.handle('POST', '/my_service', 'not_remote')

    self.VerifyResponse('400', 'Unrecognized RPC method: not_remote', '')

    self.mox.VerifyAll()

  def testRequestError(self):
    """RequestError handling."""
    def build_request(handler, request):
      raise service_handlers.RequestError('This is a request error')
    self.rpc_mapper1.build_request(
        self.handler, Request1).WithSideEffects(build_request)

    self.ExpectRpcError(self.rpc_mapper1,
                        remote.RpcState.REQUEST_ERROR,
                        'Error parsing ProtoRPC request '
                        '(This is a request error)')

    self.mox.ReplayAll()

    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('400',
                        'Error parsing ProtoRPC request '
                        '(This is a request error)',
                        '')


    self.mox.VerifyAll()

  def testDecodeError(self):
    """DecodeError handling."""
    def build_request(handler, request):
      raise messages.DecodeError('This is a decode error')
    self.rpc_mapper1.build_request(
        self.handler, Request1).WithSideEffects(build_request)

    self.ExpectRpcError(self.rpc_mapper1,
                        remote.RpcState.REQUEST_ERROR,
                        r'Error parsing ProtoRPC request '
                        r'(This is a decode error)')

    self.mox.ReplayAll()

    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('400',
                        'Error parsing ProtoRPC request '
                        '(This is a decode error)',
                        '')

    self.mox.VerifyAll()

  def testResponseException(self):
    """Test what happens when build_response raises ResponseError."""
    self.rpc_mapper1.build_request(
        self.handler, Request1).AndReturn(self.request)

    self.rpc_mapper1.build_response(
        self.handler, mox.IsA(Response1)).AndRaise(
        service_handlers.ResponseError)

    self.ExpectRpcError(self.rpc_mapper1,
                        remote.RpcState.SERVER_ERROR,
                        'Internal Server Error')

    self.mox.ReplayAll()

    self.handler.handle('POST', '/my_service', 'method1')

    self.VerifyResponse('500', 'Internal Server Error', '')

    self.mox.VerifyAll()

  def testGet(self):
    """Test that GET goes to 'handle' properly."""
    self.handler.handle = self.mox.CreateMockAnything()
    self.handler.handle('GET', '/my_service', 'method1')
    self.handler.handle('GET', '/my_other_service', 'method2')

    self.mox.ReplayAll()

    self.handler.get('/my_service', 'method1')
    self.handler.get('/my_other_service', 'method2')

    self.mox.VerifyAll()

  def testPost(self):
    """Test that POST goes to 'handle' properly."""
    self.handler.handle = self.mox.CreateMockAnything()
    self.handler.handle('POST', '/my_service', 'method1')
    self.handler.handle('POST', '/my_other_service', 'method2')

    self.mox.ReplayAll()

    self.handler.post('/my_service', 'method1')
    self.handler.post('/my_other_service', 'method2')

    self.mox.VerifyAll()

  def testGetNoMethod(self):
    self.handler.get('/my_service', '')
    self.assertEquals(405, self.handler.response.status)
    self.assertEquals(
      util.pad_string('/my_service is a ProtoRPC service.\n\n'
                      'Service %s.Service\n\n'
                      'More about ProtoRPC: '
                      'http://code.google.com/p/google-protorpc\n' %
                      __name__),
      self.handler.response.out.getvalue())
    self.assertEquals(
        'nosniff',
        self.handler.response.headers['x-content-type-options'])

  def testGetNotSupported(self):
    self.handler.get('/my_service', 'method1')
    self.assertEquals(405, self.handler.response.status)
    expected_message = ('/my_service.method1 is a ProtoRPC method.\n\n'
                        'Service %s.Service\n\n'
                        'More about ProtoRPC: '
                        'http://code.google.com/p/google-protorpc\n' %
                        __name__)
    self.assertEquals(util.pad_string(expected_message),
                      self.handler.response.out.getvalue())
    self.assertEquals(
        'nosniff',
        self.handler.response.headers['x-content-type-options'])

  def testGetUnknownContentType(self):
    self.handler.request.headers['content-type'] = 'image/png'
    self.handler.get('/my_service', 'method1')
    self.assertEquals(415, self.handler.response.status)
    self.assertEquals(
      util.pad_string('/my_service.method1 is a ProtoRPC method.\n\n'
                      'Service %s.Service\n\n'
                      'More about ProtoRPC: '
                      'http://code.google.com/p/google-protorpc\n' %
                      __name__),
      self.handler.response.out.getvalue())
    self.assertEquals(
        'nosniff',
        self.handler.response.headers['x-content-type-options'])


class MissingContentLengthTests(ServiceHandlerTest):
  """Test for when content-length is not set in the environment.

  This test moves CONTENT_LENGTH from the environment to the
  content-length header.
  """

  def GetEnvironment(self):
    environment = super(MissingContentLengthTests, self).GetEnvironment()
    content_length = str(environment.pop('CONTENT_LENGTH', '0'))
    environment['HTTP_CONTENT_LENGTH'] = content_length
    return environment


class MissingContentTypeTests(ServiceHandlerTest):
  """Test for when content-type is not set in the environment.

  This test moves CONTENT_TYPE from the environment to the
  content-type header.
  """

  def GetEnvironment(self):
    environment = super(MissingContentTypeTests, self).GetEnvironment()
    content_type = str(environment.pop('CONTENT_TYPE', ''))
    environment['HTTP_CONTENT_TYPE'] = content_type
    return environment


class RPCMapperTestBase(test_util.TestCase):

  def setUp(self):
    """Set up test framework."""
    self.Reinitialize()

  def Reinitialize(self, input='',
                   get=False,
                   path_method='method1',
                   content_type='text/plain'):
    """Allows reinitialization of test with custom input values and POST.

    Args:
      input: Query string or POST input.
      get: Use GET method if True.  Use POST if False.
    """
    self.factory = service_handlers.ServiceHandlerFactory(Service)

    self.service_handler = service_handlers.ServiceHandler(self.factory,
                                                           Service())
    self.service_handler.remote_method = path_method
    request_path = '/servicepath'
    if path_method:
      request_path += '/' + path_method
    if get:
      request_path += '?' + input

    if get:
      environ = {'wsgi.input': cStringIO.StringIO(''),
                 'CONTENT_LENGTH': '0',
                 'QUERY_STRING': input,
                 'REQUEST_METHOD': 'GET',
                 'PATH_INFO': request_path,
                }
      self.service_handler.method = 'GET'
    else:
      environ = {'wsgi.input': cStringIO.StringIO(input),
                 'CONTENT_LENGTH': str(len(input)),
                 'QUERY_STRING': '',
                 'REQUEST_METHOD': 'POST',
                 'PATH_INFO': request_path,
                }
      self.service_handler.method = 'POST'

    self.request = webapp.Request(environ)

    self.response = webapp.Response()

    self.service_handler.initialize(self.request, self.response)

    self.service_handler.request.headers['Content-Type'] = content_type


class RPCMapperTest(RPCMapperTestBase, webapp_test_util.RequestHandlerTestBase):
  """Test the RPCMapper base class."""

  def setUp(self):
    RPCMapperTestBase.setUp(self)
    webapp_test_util.RequestHandlerTestBase.setUp(self)
    self.mox = mox.Mox()
    self.protocol = self.mox.CreateMockAnything()

  def GetEnvironment(self):
    """Get environment.

    Return bogus content in body.

    Returns:
      dict of CGI environment.
    """
    environment = super(RPCMapperTest, self).GetEnvironment()
    environment['wsgi.input'] = cStringIO.StringIO('my body')
    environment['CONTENT_LENGTH'] = len('my body')
    return environment

  def testContentTypes_JustDefault(self):
    """Test content type attributes."""
    self.mox.ReplayAll()

    mapper = service_handlers.RPCMapper(['GET', 'POST'],
                                        'my-content-type',
                                        self.protocol)

    self.assertEquals(frozenset(['GET', 'POST']), mapper.http_methods)
    self.assertEquals('my-content-type', mapper.default_content_type)
    self.assertEquals(frozenset(['my-content-type']),
                                mapper.content_types)

    self.mox.VerifyAll()

  def testContentTypes_Extended(self):
    """Test content type attributes."""
    self.mox.ReplayAll()

    mapper = service_handlers.RPCMapper(['GET', 'POST'],
                                        'my-content-type',
                                        self.protocol,
                                        content_types=['a', 'b'])

    self.assertEquals(frozenset(['GET', 'POST']), mapper.http_methods)
    self.assertEquals('my-content-type', mapper.default_content_type)
    self.assertEquals(frozenset(['my-content-type', 'a', 'b']),
                                mapper.content_types)

    self.mox.VerifyAll()

  def testBuildRequest(self):
    """Test building a request."""
    expected_request = Request1()
    self.protocol.decode_message(Request1,
                                 'my body').AndReturn(expected_request)

    self.mox.ReplayAll()

    mapper = service_handlers.RPCMapper(['POST'],
                                        'my-content-type',
                                        self.protocol)

    request = mapper.build_request(self.handler, Request1)

    self.assertTrue(expected_request is request)

  def testBuildRequest_ValidationError(self):
    """Test building a request generating a validation error."""
    expected_request = Request1()
    self.protocol.decode_message(
        Request1, 'my body').AndRaise(messages.ValidationError('xyz'))

    self.mox.ReplayAll()

    mapper = service_handlers.RPCMapper(['POST'],
                                        'my-content-type',
                                        self.protocol)

    self.assertRaisesWithRegexpMatch(
        service_handlers.RequestError,
        'Unable to parse request content: xyz',
        mapper.build_request,
        self.handler,
        Request1)

  def testBuildRequest_DecodeError(self):
    """Test building a request generating a decode error."""
    expected_request = Request1()
    self.protocol.decode_message(
        Request1, 'my body').AndRaise(messages.DecodeError('xyz'))

    self.mox.ReplayAll()

    mapper = service_handlers.RPCMapper(['POST'],
                                        'my-content-type',
                                        self.protocol)

    self.assertRaisesWithRegexpMatch(
        service_handlers.RequestError,
        'Unable to parse request content: xyz',
        mapper.build_request,
        self.handler,
        Request1)

  def testBuildResponse(self):
    """Test building a response."""
    response = Response1()
    self.protocol.encode_message(response).AndReturn('encoded')

    self.mox.ReplayAll()

    mapper = service_handlers.RPCMapper(['POST'],
                                        'my-content-type',
                                        self.protocol)

    request = mapper.build_response(self.handler, response)

    self.assertEquals('my-content-type',
                      self.handler.response.headers['Content-Type'])
    self.assertEquals('encoded', self.handler.response.out.getvalue())

  def testBuildResponse(self):
    """Test building a response."""
    response = Response1()
    self.protocol.encode_message(response).AndRaise(
        messages.ValidationError('xyz'))

    self.mox.ReplayAll()

    mapper = service_handlers.RPCMapper(['POST'],
                                        'my-content-type',
                                        self.protocol)

    self.assertRaisesWithRegexpMatch(service_handlers.ResponseError,
                                     'Unable to encode message: xyz',
                                     mapper.build_response,
                                     self.handler,
                                     response)


class ProtocolMapperTestBase(object):
  """Base class for basic protocol mapper tests."""

  def setUp(self):
    """Reinitialize test specifically for protocol buffer mapper."""
    super(ProtocolMapperTestBase, self).setUp()
    self.Reinitialize(path_method='my_method',
                      content_type='application/x-google-protobuf')

    self.request_message = Request1()
    self.request_message.integer_field = 1
    self.request_message.string_field = u'something'
    self.request_message.enum_field = Enum1.VAL1

    self.response_message = Response1()
    self.response_message.integer_field = 1
    self.response_message.string_field = u'something'
    self.response_message.enum_field = Enum1.VAL1

  def testBuildRequest(self):
    """Test request building."""
    self.Reinitialize(self.protocol.encode_message(self.request_message),
                      content_type=self.content_type)

    mapper = self.mapper()
    parsed_request = mapper.build_request(self.service_handler,
                                          Request1)
    self.assertEquals(self.request_message, parsed_request)

  def testBuildResponse(self):
    """Test response building."""

    mapper = self.mapper()
    mapper.build_response(self.service_handler, self.response_message)
    self.assertEquals(self.protocol.encode_message(self.response_message),
                      self.service_handler.response.out.getvalue())

  def testWholeRequest(self):
    """Test the basic flow of a request with mapper class."""
    body = self.protocol.encode_message(self.request_message)
    self.Reinitialize(input=body,
                      content_type=self.content_type)
    self.factory.add_request_mapper(self.mapper())
    self.service_handler.handle('POST', '/my_service', 'method1')
    VerifyResponse(self,
                   self.service_handler.response,
                   '200',
                   'OK',
                   self.protocol.encode_message(self.response_message),
                   self.content_type)


class URLEncodedRPCMapperTest(ProtocolMapperTestBase, RPCMapperTestBase):
  """Test the URL encoded RPC mapper."""

  content_type = 'application/x-www-form-urlencoded'
  protocol = protourlencode
  mapper = service_handlers.URLEncodedRPCMapper

  def testBuildRequest_Prefix(self):
    """Test building request with parameter prefix."""
    self.Reinitialize(urllib.urlencode([('prefix_integer_field', '10'),
                                        ('prefix_string_field', 'a string'),
                                        ('prefix_enum_field', 'VAL1'),
                                       ]),
                      self.content_type)

    url_encoded_mapper = service_handlers.URLEncodedRPCMapper(
        parameter_prefix='prefix_')
    request = url_encoded_mapper.build_request(self.service_handler,
                                               Request1)
    self.assertEquals(10, request.integer_field)
    self.assertEquals('a string', request.string_field)
    self.assertEquals(Enum1.VAL1, request.enum_field)

  def testBuildRequest_DecodeError(self):
    """Test trying to build request that causes a decode error."""
    self.Reinitialize(urllib.urlencode((('integer_field', '10'),
                                        ('integer_field', '20'),
                                        )),
                      content_type=self.content_type)

    url_encoded_mapper = service_handlers.URLEncodedRPCMapper()

    self.assertRaises(service_handlers.RequestError,
                      url_encoded_mapper.build_request,
                      self.service_handler,
                      Service.method1.remote.request_type)

  def testBuildResponse_Prefix(self):
    """Test building a response with parameter prefix."""
    response = Response1()
    response.integer_field = 10
    response.string_field = u'a string'
    response.enum_field = Enum1.VAL3

    url_encoded_mapper = service_handlers.URLEncodedRPCMapper(
        parameter_prefix='prefix_')

    url_encoded_mapper.build_response(self.service_handler, response)
    self.assertEquals('application/x-www-form-urlencoded',
                      self.response.headers['content-type'])
    self.assertEquals(cgi.parse_qs(self.response.out.getvalue(), True, True),
                      {'prefix_integer_field': ['10'],
                       'prefix_string_field': [u'a string'],
                       'prefix_enum_field': ['VAL3'],
                      })


class ProtobufRPCMapperTest(ProtocolMapperTestBase, RPCMapperTestBase):
  """Test the protobuf encoded RPC mapper."""

  content_type = 'application/octet-stream'
  protocol = protobuf
  mapper = service_handlers.ProtobufRPCMapper


class JSONRPCMapperTest(ProtocolMapperTestBase, RPCMapperTestBase):
  """Test the URL encoded RPC mapper."""

  content_type = 'application/json'
  protocol = protojson
  mapper = service_handlers.JSONRPCMapper


class MyService(remote.Service):

  def __init__(self, value='default'):
    self.value = value


class ServiceMappingTest(test_util.TestCase):

  def CheckFormMappings(self, mapping, registry_path='/protorpc'):
    """Check to make sure that form mapping is configured as expected.

    Args:
      mapping: Mapping that should contain forms handlers.
    """
    pattern, factory = mapping[0]
    self.assertEquals('%s/form(?:/)?' % registry_path, pattern)
    handler = factory()
    self.assertTrue(isinstance(handler, forms.FormsHandler))
    self.assertEquals(registry_path, handler.registry_path)

    pattern, factory = mapping[1]
    self.assertEquals('%s/form/(.+)' % registry_path, pattern)
    self.assertEquals(forms.ResourceHandler, factory)


  def DoMappingTest(self,
                    services,
                    registry_path='/myreg',
                    expected_paths=None):
    mapped_services = mapping = service_handlers.service_mapping(services,
                                                                 registry_path)
    if registry_path:
      form_mapping = mapping[:2]
      mapped_registry_path, mapped_registry_factory = mapping[-1]
      mapped_services = mapping[2:-1]
      self.CheckFormMappings(form_mapping, registry_path=registry_path)

      self.assertEquals(r'(%s)%s' % (registry_path,
                                     service_handlers._METHOD_PATTERN),
                        mapped_registry_path)
      self.assertEquals(registry.RegistryService,
                        mapped_registry_factory.service_factory.service_class)

      # Verify registry knows about other services.
      expected_registry = {registry_path: registry.RegistryService}
      for path, factory in dict(services).items():
        if isinstance(factory, type) and issubclass(factory, remote.Service):
          expected_registry[path] = factory
        else:
          expected_registry[path] = factory.service_class
      self.assertEquals(expected_registry,
                        mapped_registry_factory().service.registry)

    # Verify that services are mapped to URL.
    self.assertEquals(len(services), len(mapped_services))
    for path, service in dict(services).items():
      mapped_path = r'(%s)%s' %  (path, service_handlers._METHOD_PATTERN)
      mapped_factory = dict(mapped_services)[mapped_path]
      self.assertEquals(service, mapped_factory.service_factory)

  def testServiceMapping_Empty(self):
    """Test an empty service mapping."""
    self.DoMappingTest({})

  def testServiceMapping_ByClass(self):
    """Test mapping a service by class."""
    self.DoMappingTest({'/my-service': MyService})

  def testServiceMapping_ByFactory(self):
    """Test mapping a service by factory."""
    self.DoMappingTest({'/my-service': MyService.new_factory('new-value')})

  def testServiceMapping_ByList(self):
    """Test mapping a service by factory."""
    self.DoMappingTest(
      [('/my-service1', MyService.new_factory('service1')),
       ('/my-service2', MyService.new_factory('service2')),
      ])

  def testServiceMapping_NoRegistry(self):
    """Test mapping a service by class."""
    mapping = self.DoMappingTest({'/my-service': MyService}, None)

  def testDefaultMappingWithClass(self):
    """Test setting path just from the class.

    Path of the mapping will be the fully qualified ProtoRPC service name with
    '.' replaced with '/'.  For example:

      com.nowhere.service.TheService -> /com/nowhere/service/TheService
    """
    mapping = service_handlers.service_mapping([MyService])
    mapped_services = mapping[2:-1]
    self.assertEquals(1, len(mapped_services))
    path, factory = mapped_services[0]

    self.assertEquals(
      r'(/test_package/MyService)' + service_handlers._METHOD_PATTERN,
      path)
    self.assertEquals(MyService, factory.service_factory)

  def testDefaultMappingWithFactory(self):
    mapping = service_handlers.service_mapping(
      [MyService.new_factory('service1')])
    mapped_services = mapping[2:-1]
    self.assertEquals(1, len(mapped_services))
    path, factory = mapped_services[0]

    self.assertEquals(
      r'(/test_package/MyService)' + service_handlers._METHOD_PATTERN,
      path)
    self.assertEquals(MyService, factory.service_factory.service_class)

  def testMappingDuplicateExplicitServiceName(self):
    self.assertRaisesWithRegexpMatch(
      service_handlers.ServiceConfigurationError,
      "Path '/my_path' is already defined in service mapping",
      service_handlers.service_mapping,
      [('/my_path', MyService),
       ('/my_path', MyService),
       ])

  def testMappingDuplicateServiceName(self):
    self.assertRaisesWithRegexpMatch(
      service_handlers.ServiceConfigurationError,
      "Path '/test_package/MyService' is already defined in service mapping",
      service_handlers.service_mapping,
      [MyService, MyService])


class GetCalled(remote.Service):

  def __init__(self, test):
    self.test = test

  @remote.method(Request1, Response1)
  def my_method(self, request):
    self.test.request = request
    return Response1(string_field='a response')


class TestRunServices(test_util.TestCase):

  def DoRequest(self,
                path,
                request,
                response_type,
                reg_path='/protorpc'):
    stdin = sys.stdin
    stdout = sys.stdout
    environ = os.environ
    try:
      sys.stdin = cStringIO.StringIO(protojson.encode_message(request))
      sys.stdout = cStringIO.StringIO()

      os.environ = webapp_test_util.GetDefaultEnvironment()
      os.environ['PATH_INFO'] = path
      os.environ['REQUEST_METHOD'] = 'POST'
      os.environ['CONTENT_TYPE'] = 'application/json'
      os.environ['wsgi.input'] = sys.stdin
      os.environ['wsgi.output'] = sys.stdout
      os.environ['CONTENT_LENGTH'] = len(sys.stdin.getvalue())

      service_handlers.run_services(
        [('/my_service', GetCalled.new_factory(self))], reg_path)

      header, body = sys.stdout.getvalue().split('\n\n', 1)

      return (header.split('\n')[0],
              protojson.decode_message(response_type, body))
    finally:
      sys.stdin = stdin
      sys.stdout = stdout
      os.environ = environ

  def testRequest(self):
    request = Request1(string_field='request value')

    status, response = self.DoRequest('/my_service.my_method',
                                      request,
                                      Response1)
    self.assertEquals('Status: 200 OK', status)
    self.assertEquals(request, self.request)
    self.assertEquals(Response1(string_field='a response'), response)

  def testRegistry(self):
    request = Request1(string_field='request value')
    status, response = self.DoRequest('/protorpc.services',
                              message_types.VoidMessage(),
                              registry.ServicesResponse)

    self.assertEquals('Status: 200 OK', status)
    self.assertIterEqual([
        registry.ServiceMapping(
            name='/protorpc',
            definition='protorpc.registry.RegistryService'),
        registry.ServiceMapping(
            name='/my_service',
            definition='test_package.GetCalled'),
        ], response.services)

  def testRunServicesWithOutRegistry(self):
    request = Request1(string_field='request value')

    status, response = self.DoRequest('/protorpc.services',
                                      message_types.VoidMessage(),
                                      registry.ServicesResponse,
                                      reg_path=None)
    self.assertEquals('Status: 404 Not Found', status)


def main():
  unittest.main()


if __name__ == '__main__':
  main()
