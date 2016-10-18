# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dashboard.pinpoint.models import attempt


class Dep(ndb.Model):
  """A git repository pinned to a particular commit."""
  repository = ndb.StringProperty(required=True)
  git_hash = ndb.StringProperty(required=True)


class Change(ndb.Model):
  """A particular set of Deps with or without an additional patch applied.

  For example, a Change might sync to chromium/src@9064a40 and catapult@8f26966,
  then apply patch 2423293002.
  """
  base_commit = ndb.LocalStructuredProperty(Dep, required=True)
  deps = ndb.LocalStructuredProperty(Dep, repeated=True)
  patch = ndb.StringProperty()  # TODO: Not sure what type this will be yet.

  # The results of running Quests on Changes.
  attempts = ndb.LocalStructuredProperty(attempt.Attempt, repeated=True)
