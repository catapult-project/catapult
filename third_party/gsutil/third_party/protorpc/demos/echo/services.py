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

"""Echo service demo.

Implements a simple echo service.  The request and response objects are
the same message that contains numerous different fields useful for testing and
illustrating the forms interface.
"""

__author__ = 'rafek@google.com (Rafe Kaplan)'

import appengine_config

import logging
import time

from protorpc import messages
from protorpc import remote
from protorpc.webapp import service_handlers

package = 'protorpc.echo'


class SubMessage(messages.Message):
  """A sub-message that can be required by EchoData."""

  value = messages.StringField(1)


class EchoData(messages.Message):
  """Echo message.

  Contains all relevant ProtoRPC data-types including recursive reference
  to itself in nested and repeated form.
  """

  class Color(messages.Enum):
    """A simple enumeration type."""

    RED = 1
    GREEN = 2
    BLUE = 3

  # A required field with a default.
  required = messages.EnumField(Color, 1,
                                required=True,
                                default=Color.BLUE)
  required_message = messages.MessageField(SubMessage, 18, required=True)

  # Optional fields.
  a_string = messages.StringField(2)
  an_int = messages.IntegerField(3)
  a_float = messages.FloatField(4)
  a_bool = messages.BooleanField(5)
  a_bytes = messages.BytesField(6)
  a_color = messages.EnumField(Color, 7)
  an_echo = messages.MessageField('EchoData', 8)

  # Repeated fields.
  strings = messages.StringField(9, repeated=True)
  ints = messages.IntegerField(10, repeated=True)
  floats = messages.FloatField(11, repeated=True)
  bools = messages.BooleanField(12, repeated=True);
  bytes = messages.BytesField(13, repeated=True)
  colors = messages.EnumField(Color, 14, repeated=True)
  echos = messages.MessageField('EchoData', 15, repeated=True)

  # With defaults
  default_string = messages.StringField(19, default='a default')
  default_int = messages.IntegerField(20, default=30)
  default_float = messages.FloatField(21, default=3.1415)
  default_bool = messages.BooleanField(22, default=True)
  default_bytes = messages.BytesField(23, default='YSBieXRlcw==')
  default_color = messages.EnumField(Color, 24, default=Color.GREEN)

  # If want_time is set to True, the response will contain current seconds
  # since epoch.
  want_time = messages.BooleanField(16)
  time = messages.IntegerField(17)


class EchoService(remote.Service):
  """Echo service echos response to client."""

  @remote.method(EchoData, EchoData)
  def echo(self, request):
    """Echo method."""
    logging.info('\n'.join(
      ['Received request:',
       '  Host       = %s' % self.request_state.remote_host,
       '  IP Address = %s' % self.request_state.remote_address,
      ]))
    if request.want_time:
      request.time = int(time.time())
    return request


def main():
  service_handlers.run_services(
    [('/echo', EchoService),
    ])


if __name__ == '__main__':
  main()
