# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class GCECreationInfo(ndb.Model):
  source_disk_image = ndb.StringProperty(indexed=True)
  machine_type = ndb.StringProperty(indexed=True)
  zone = ndb.StringProperty(indexed=True)
