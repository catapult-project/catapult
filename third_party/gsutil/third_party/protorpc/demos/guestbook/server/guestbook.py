#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
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

import cgi
import datetime
import time
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp

from protorpc import message_types
from protorpc import messages
from protorpc import remote
from protorpc.webapp import service_handlers


class Greeting(db.Model):
  author = db.UserProperty()
  content = db.StringProperty(multiline=True)
  date = db.DateTimeProperty(auto_now_add=True)


class MainPage(webapp.RequestHandler):
  def get(self):
    self.response.out.write('<html><body>')

    greetings = db.GqlQuery("SELECT * "
                            "FROM Greeting "
                            "ORDER BY date DESC LIMIT 10")

    for greeting in greetings:
      if greeting.author:
        self.response.out.write('<b>%s</b> wrote:' % greeting.author.nickname())
      else:
        self.response.out.write('An anonymous person wrote:')
      self.response.out.write('<blockquote>%s</blockquote>' %
                              cgi.escape(greeting.content))


    self.response.out.write("""
          <form action="/sign" method="post">
            <div><textarea name="content" rows="3" cols="60"></textarea></div>
            <div><input type="submit" value="Sign Guestbook"></div>
          </form>
        </body>
      </html>""")


class Guestbook(webapp.RequestHandler):
  def post(self):
    greeting = Greeting()

    if users.get_current_user():
      greeting.author = users.get_current_user()

    greeting.content = self.request.get('content')
    greeting.put()
    self.redirect('/')


class Note(messages.Message):

  text = messages.StringField(1, required=True)
  when = messages.IntegerField(2)


class GetNotesRequest(messages.Message):

  limit = messages.IntegerField(1, default=10)
  on_or_before = messages.IntegerField(2)

  class Order(messages.Enum):
   WHEN = 1
   TEXT = 2
  order = messages.EnumField(Order, 3, default=Order.WHEN)


class Notes(messages.Message):
  notes = messages.MessageField(Note, 1, repeated=True)


class PostService(remote.Service):

  # Add the remote decorator to indicate the service methods
  @remote.method(Note)
  def post_note(self, request):

    # If the Note instance has a timestamp, use that timestamp
    if request.when is not None:
      when = datetime.datetime.utcfromtimestamp(request.when)

    # Else use the current time
    else:
      when = datetime.datetime.now()
    note = Greeting(content=request.text, date=when)
    note.put()
    return message_types.VoidMessage()

  @remote.method(GetNotesRequest, Notes)
  def get_notes(self, request):
   query = Greeting.all().order('-date')

   if request.on_or_before:
    when = datetime.datetime.utcfromtimestamp(
       request.on_or_before)
    query.filter('date <=', when)

   notes = []
   for note_model in query.fetch(request.limit):
    if note_model.date:
      when = int(time.mktime(note_model.date.utctimetuple()))
    else:
      when = None
    note = Note(text=note_model.content, when=when)
    notes.append(note)

   if request.order == GetNotesRequest.Order.TEXT:
    notes.sort(key=lambda note: note.text)

   return Notes(notes=notes)


service_mapping = service_handlers.service_mapping(
    [('/postservice', PostService)])

application = webapp.WSGIApplication([
  ('/', MainPage),
  ('/sign', Guestbook),
] + service_mapping,
debug=True)


def main():
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
