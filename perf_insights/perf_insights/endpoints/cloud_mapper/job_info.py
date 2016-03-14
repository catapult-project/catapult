# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class JobInfo(ndb.Model):
  date = ndb.DateTimeProperty(auto_now_add=True, indexed=True)
  status = ndb.StringProperty(indexed=True)
  remote_addr = ndb.StringProperty(indexed=True)

  mapper = ndb.TextProperty()
  reducer = ndb.TextProperty()
  mapper_function = ndb.StringProperty(indexed=True)
  reducer_function = ndb.StringProperty(indexed=True)
  query = ndb.StringProperty(indexed=True)
  corpus = ndb.StringProperty(indexed=True)
  revision = ndb.StringProperty(indexed=True)
  timeout = ndb.IntegerProperty()
  function_timeout = ndb.IntegerProperty()

  running_tasks = ndb.StringProperty(repeated=True)

  running_tasks = ndb.StringProperty(repeated=True)

  results = ndb.StringProperty(indexed=True)
