# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from google.appengine.api import users
from google.appengine.ext import ndb

from dashboard import bot_whitelist
from dashboard import testing_common
from dashboard import xsrf


class BotWhitelistTest(testing_common.TestCase):

  def setUp(self):
    super(BotWhitelistTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/bot_whitelist', bot_whitelist.BotWhitelistHandler)])
    self.testapp = webtest.TestApp(app)

  def testGet(self):
    whitelist = bot_whitelist.BotWhitelist(
        id=bot_whitelist.WHITELIST_KEY,
        bots=['linux-release', 'linux-release-lowmem'])
    whitelist.put()
    response = self.testapp.get('/bot_whitelist')
    textarea_value = response.html('textarea')[0].renderContents()
    self.assertEqual('linux-release\nlinux-release-lowmem', textarea_value)

  def testGet_EmptyWhitelist(self):
    response = self.testapp.get('/bot_whitelist')
    textarea_value = response.html('textarea')[0].renderContents()
    self.assertEqual('', textarea_value)

  def testPost_InitializeWhitelist(self):
    self.SetCurrentUser('sullivan@google.com', is_admin=True)
    self.testapp.post('/bot_whitelist', {
        'bot_whitelist': 'linux-release\nandroid-gn\nchromium-rel-mac6',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    whitelist = ndb.Key('BotWhitelist', bot_whitelist.WHITELIST_KEY).get()
    self.assertEqual(
        ['linux-release', 'android-gn', 'chromium-rel-mac6'], whitelist.bots)

  def testPost_UpdateWhitelist(self):
    self.SetCurrentUser('sullivan@google.com', is_admin=True)
    whitelist = bot_whitelist.BotWhitelist(
        id=bot_whitelist.WHITELIST_KEY,
        bots=['linux-release', 'chromium-rel-mac6'])
    self.testapp.post('/bot_whitelist', {
        'bot_whitelist': 'linux-release\nchromium-rel-win7\nandroid-gn',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    whitelist = ndb.Key('BotWhitelist', bot_whitelist.WHITELIST_KEY).get()
    self.assertEqual(
        ['linux-release', 'chromium-rel-win7', 'android-gn'], whitelist.bots)

  def testPost_ClearWhitelist(self):
    self.SetCurrentUser('sullivan@google.com', is_admin=True)
    whitelist = bot_whitelist.BotWhitelist(id=bot_whitelist.WHITELIST_KEY,
                                           bots=['linux-release', 'android-gn'])
    self.testapp.post('/bot_whitelist', {
        'bot_whitelist': '',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    whitelist = ndb.Key('BotWhitelist', bot_whitelist.WHITELIST_KEY).get()
    self.assertEqual([], whitelist.bots)


if __name__ == '__main__':
  unittest.main()
