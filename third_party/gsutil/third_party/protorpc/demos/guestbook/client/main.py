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

import appengine_config

import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

from protorpc import transport
from protorpc import protojson

import guestbook


postservice = guestbook.PostService.Stub(
  transport.HttpTransport('http://postservice-demo.appspot.com/postservice'))


class MainHandler(webapp.RequestHandler):
  def get(self):
    notes = postservice.get_notes(limit=10)
    self.response.out.write('Last %d posts...' % len(notes.notes))
    for note in notes.notes:
      self.response.out.write('<p>%s' % note.text)


def main():
  application = webapp.WSGIApplication([('/', MainHandler)],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
