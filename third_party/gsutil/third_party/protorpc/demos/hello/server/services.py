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

import appengine_config

from protorpc import messages
from protorpc import remote
from protorpc.webapp import service_handlers


class HelloRequest(messages.Message):

  my_name = messages.StringField(1, required=True)


class HelloResponse(messages.Message):

  hello = messages.StringField(1, required=True)


class HelloService(remote.Service):

  @remote.method(HelloRequest, HelloResponse)
  def hello(self, request):
    return HelloResponse(hello='Hello there, %s!' % request.my_name)


def main():
  service_handlers.run_services([('/hello', HelloService)])


if __name__ == '__main__':
  main()
