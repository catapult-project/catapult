# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class TraceInfo(ndb.Model):
  date = ndb.DateTimeProperty(auto_now_add=True, indexed=True)
  prod = ndb.StringProperty(indexed=True)
  remote_addr = ndb.StringProperty(indexed=True)
  tags = ndb.StringProperty(indexed=True, repeated=True)
  user_agent = ndb.StringProperty(indexed=True, default=None)
  ver = ndb.StringProperty(indexed=True)
