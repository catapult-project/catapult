#!/usr/bin/env python2.7
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

class TraceInfo(ndb.Model):
  prod = ndb.StringProperty(indexed=False)
  ver = ndb.StringProperty(indexed=False)
  remote_addr = ndb.StringProperty(indexed=False)
  date = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
