# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for ip_whitelist module."""

__author__ = 'sullivan@google.com (Annie Sullivan)'

import unittest

import webapp2
import webtest

from google.appengine.api import users
from google.appengine.ext import ndb

from dashboard import ip_whitelist
from dashboard import testing_common
from dashboard import xsrf


class IpWhitelistTest(testing_common.TestCase):

  def setUp(self):
    super(IpWhitelistTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/ip_whitelist', ip_whitelist.IpWhitelistHandler)])
    self.testapp = webtest.TestApp(app)

  def testGet_NonEmptyWhitelist_ListsIPsInTextarea(self):
    whitelist = ip_whitelist.IpWhitelist(
        id=ip_whitelist.WHITELIST_KEY, ips=['172.16.241.1', '123.123.123.4'])
    whitelist.put()
    response = self.testapp.get('/ip_whitelist')
    textarea_value = response.html('textarea')[0].renderContents()
    self.assertEqual('172.16.241.1\n123.123.123.4', textarea_value)

  def testGet_EmptyWhitelist_ShowsEmptyTextArea(self):
    response = self.testapp.get('/ip_whitelist')
    textarea_value = response.html('textarea')[0].renderContents()
    self.assertEqual('', textarea_value)

  def testPost_NoPreviousWhitelist_InitializesWhitelist(self):
    self.SetCurrentUser('sullivan@google.com', is_admin=True)
    self.testapp.post('/ip_whitelist', {
        'ip_whitelist': '123.45.6.78\n98.76.54.32\n127.0.0.1',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    whitelist = ndb.Key('IpWhitelist', ip_whitelist.WHITELIST_KEY).get()
    self.assertEqual(['123.45.6.78', '98.76.54.32', '127.0.0.1'], whitelist.ips)

  def testPost_WithPreviousWhitelsit_UpdatesWhitelist(self):
    self.SetCurrentUser('sullivan@google.com', is_admin=True)
    whitelist = ip_whitelist.IpWhitelist(id=ip_whitelist.WHITELIST_KEY,
                                         ips=['172.16.241.1', '123.123.123.4'])
    self.testapp.post('/ip_whitelist', {
        'ip_whitelist': '123.45.6.78\n98.76.54.32\n127.0.0.1',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    whitelist = ndb.Key('IpWhitelist', ip_whitelist.WHITELIST_KEY).get()
    self.assertEqual(['123.45.6.78', '98.76.54.32', '127.0.0.1'], whitelist.ips)

  def testPost_WithEmptyIPWhitelistParam_ClearsWhitelist(self):
    self.SetCurrentUser('sullivan@google.com', is_admin=True)
    whitelist = ip_whitelist.IpWhitelist(id=ip_whitelist.WHITELIST_KEY,
                                         ips=['172.16.241.1', '123.123.123.4'])
    self.testapp.post('/ip_whitelist', {
        'ip_whitelist': '',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    whitelist = ndb.Key('IpWhitelist', ip_whitelist.WHITELIST_KEY).get()
    self.assertEqual([], whitelist.ips)


if __name__ == '__main__':
  unittest.main()
