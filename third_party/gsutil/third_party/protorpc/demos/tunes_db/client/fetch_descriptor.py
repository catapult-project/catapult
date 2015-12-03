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

"""Boot-strap development by fetching package set from service.

This script fetches a protobuf encoded FileSet from get_file_set
method of a service.
"""

__author__ = 'rafek@google.com (Rafe Kaplan)'

import optparse
import os
import sys
import urllib2

from protorpc import protobuf
from protorpc import protojson
from protorpc import registry
from protorpc import transport


def parse_options(argv):
  """Parse options.

  Args:
    argv: List of original unparsed options.

  Returns:
    Options object as parsed by optparse.
  """
  program = os.path.split(__file__)[-1]
  parser = optparse.OptionParser(usage='%s [options]' % program)

  parser.add_option('-o', '--output',
                    dest='output',
                    help='Write descriptor to FILE.',
                    metavar='FILE',
                    default='music_service.descriptor')

  parser.add_option('-r', '--registry_path',
                    dest='registry_path',
                    help='Path to registry service.',
                    metavar='REGISTRY_PATH',
                    default='/protorpc')

  parser.add_option('-s', '--server',
                    dest='server',
                    help='Tunes DB server.',
                    metavar='SERVER',
                    default='tunes-db.appspot.com')

  options, args = parser.parse_args(argv)

  if args:
    parser.print_help()
    sys.exit(1)

  return options


def main(argv):
  options = parse_options(argv[1:])

  registry_url =  'http://%s%s' % (options.server,
                                   options.registry_path)

  http_transport = transport.HttpTransport(registry_url, protocol=protojson)
  remote_registry = registry.RegistryService.Stub(http_transport)

  # Get complete list of services.
  services = remote_registry.services()

  # Get file set for all services on server.
  get_file_set = registry.GetFileSetRequest()
  get_file_set.names = [service.name for service in services.services]
  file_set = remote_registry.get_file_set(get_file_set).file_set

  # Save file sets to disk.
  output = open(options.output, 'wb')
  try:
    output.write(protobuf.encode_message(file_set))
  finally:
    output.close()


if __name__ == '__main__':
  main(sys.argv)
