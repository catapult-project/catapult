#!/usr/bin/env python
#
# Copyright 2011 Google Inc.
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

"""WSGI application tests."""

__author__ = 'rafek@google.com (Rafe Kaplan)'


import unittest


from protorpc import end2end_test
from protorpc import protojson
from protorpc import remote
from protorpc import registry
from protorpc import transport
from protorpc import test_util
from protorpc import webapp_test_util
from protorpc.wsgi import service
from protorpc.wsgi import util


class ServiceMappingTest(end2end_test.EndToEndTest):

  def setUp(self):
    self.protocols = None
    remote.Protocols.set_default(remote.Protocols.new_default())
    super(ServiceMappingTest, self).setUp()

  def CreateServices(self):

    return my_service, my_other_service

  def  CreateWsgiApplication(self):
    """Create WSGI application used on the server side for testing."""
    my_service = service.service_mapping(webapp_test_util.TestService,
                                         '/my/service')
    my_other_service = service.service_mapping(
      webapp_test_util.TestService.new_factory('initialized'),
      '/my/other_service',
      protocols=self.protocols)

    return util.first_found([my_service, my_other_service])

  def testAlternateProtocols(self):
    self.protocols = remote.Protocols()
    self.protocols.add_protocol(protojson, 'altproto', 'image/png')

    global_protocols = remote.Protocols()
    global_protocols.add_protocol(protojson, 'server-side-name', 'image/png')
    remote.Protocols.set_default(global_protocols)
    self.ResetServer()

    self.connection = transport.HttpTransport(
      self.service_url, protocol=self.protocols.lookup_by_name('altproto'))
    self.stub = webapp_test_util.TestService.Stub(self.connection)

    self.stub.optional_message(string_value='alternate-protocol')

  def testAlwaysUseDefaults(self):
    new_protocols = remote.Protocols()
    new_protocols.add_protocol(protojson, 'altproto', 'image/png')

    self.connection = transport.HttpTransport(
      self.service_url, protocol=new_protocols.lookup_by_name('altproto'))
    self.stub = webapp_test_util.TestService.Stub(self.connection)

    self.assertRaisesWithRegexpMatch(
      remote.ServerError,
      'HTTP Error 415: Unsupported Media Type',
      self.stub.optional_message, string_value='alternate-protocol')

    remote.Protocols.set_default(new_protocols)

    self.stub.optional_message(string_value='alternate-protocol')


class ProtoServiceMappingsTest(ServiceMappingTest):

  def  CreateWsgiApplication(self):
    """Create WSGI application used on the server side for testing."""
    return service.service_mappings(
      [('/my/service', webapp_test_util.TestService),
       ('/my/other_service',
        webapp_test_util.TestService.new_factory('initialized'))
      ])

  def GetRegistryStub(self, path='/protorpc'):
    service_url = self.make_service_url(path)
    transport = self.CreateTransport(service_url)
    return registry.RegistryService.Stub(transport)

  def testRegistry(self):
    registry_client = self.GetRegistryStub()
    response = registry_client.services()
    self.assertIterEqual([
        registry.ServiceMapping(
            name='/my/other_service',
            definition='protorpc.webapp_test_util.TestService'),
        registry.ServiceMapping(
            name='/my/service',
            definition='protorpc.webapp_test_util.TestService'),
        ], response.services)

  def testRegistryDictionary(self):
    self.ResetServer(service.service_mappings(
      {'/my/service': webapp_test_util.TestService,
       '/my/other_service':
           webapp_test_util.TestService.new_factory('initialized'),
      }))
    registry_client = self.GetRegistryStub()
    response = registry_client.services()
    self.assertIterEqual([
        registry.ServiceMapping(
            name='/my/other_service',
            definition='protorpc.webapp_test_util.TestService'),
        registry.ServiceMapping(
            name='/my/service',
            definition='protorpc.webapp_test_util.TestService'),
        ], response.services)

  def testNoRegistry(self):
    self.ResetServer(service.service_mappings(
      [('/my/service', webapp_test_util.TestService),
       ('/my/other_service',
        webapp_test_util.TestService.new_factory('initialized'))
      ],
      registry_path=None))
    registry_client = self.GetRegistryStub()
    self.assertRaisesWithRegexpMatch(
      remote.ServerError,
      'HTTP Error 404: Not Found',
      registry_client.services)

  def testAltRegistry(self):
    self.ResetServer(service.service_mappings(
      [('/my/service', webapp_test_util.TestService),
       ('/my/other_service',
        webapp_test_util.TestService.new_factory('initialized'))
      ],
      registry_path='/registry'))
    registry_client = self.GetRegistryStub('/registry')
    services = registry_client.services()
    self.assertTrue(isinstance(services, registry.ServicesResponse))
    self.assertIterEqual(
        [registry.ServiceMapping(
            name='/my/other_service',
            definition='protorpc.webapp_test_util.TestService'),
         registry.ServiceMapping(
             name='/my/service',
             definition='protorpc.webapp_test_util.TestService'),
        ],
        services.services)

  def testDuplicateRegistryEntry(self):
    self.assertRaisesWithRegexpMatch(
      remote.ServiceConfigurationError,
      "Path '/my/service' is already defined in service mapping",
      service.service_mappings,
      [('/my/service', webapp_test_util.TestService),
       ('/my/service',
        webapp_test_util.TestService.new_factory('initialized'))
      ])

  def testRegex(self):
    self.ResetServer(service.service_mappings(
      [('/my/[0-9]+', webapp_test_util.TestService.new_factory('service')),
       ('/my/[a-z]+',
            webapp_test_util.TestService.new_factory('other-service')),
      ]))
    my_service_url = 'http://localhost:%d/my/12345' % self.port
    my_other_service_url = 'http://localhost:%d/my/blarblar' % self.port

    my_service = webapp_test_util.TestService.Stub(
      transport.HttpTransport(my_service_url))
    my_other_service = webapp_test_util.TestService.Stub(
      transport.HttpTransport(my_other_service_url))

    response = my_service.init_parameter()
    self.assertEquals('service', response.string_value)

    response = my_other_service.init_parameter()
    self.assertEquals('other-service', response.string_value)


def main():
  unittest.main()


if __name__ == '__main__':
  main()
