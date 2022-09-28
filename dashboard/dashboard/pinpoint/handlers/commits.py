# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.api import api_request_handler
from dashboard.pinpoint.models import change
from dashboard.services import request
from dashboard.common import utils

if utils.IsRunningFlask():
  from flask import request as flask_request

  def _CheckUser():
    pass

  @api_request_handler.RequestHandlerDecoratorFactory(_CheckUser)
  def CommitsHandlerPost():
    try:
      repository = utils.SanitizeArgs(
          args=flask_request.args, key_name='repository', default='chromium')
      start_git_hash = utils.SanitizeArgs(
          args=flask_request.args, key_name='start_git_hash', default='HEAD')
      end_git_hash = utils.SanitizeArgs(
          args=flask_request.args, key_name='end_git_hash', default='HEAD')
      c1 = change.Commit.FromDict({
          'repository': repository,
          'git_hash': start_git_hash,
      })
      c2 = change.Commit.FromDict({
          'repository': repository,
          'git_hash': end_git_hash,
      })
      commits = change.Commit.CommitRange(c1, c2)
      commits = [
          change.Commit(repository, c['commit']).AsDict() for c in commits
      ]
      return [c1.AsDict()] + commits
    except request.RequestError as e:
      raise api_request_handler.BadRequestError(str(e))
else:
  class Commits(api_request_handler.ApiRequestHandler):
    # pylint: disable=abstract-method

    def _CheckUser(self):
      pass

    def Post(self, *args, **kwargs):
      del args, kwargs  # Unused.
      try:
        repository = self.request.get('repository', 'chromium')
        c1 = change.Commit.FromDict({
            'repository': repository,
            'git_hash': self.request.get('start_git_hash'),
        })
        c2 = change.Commit.FromDict({
            'repository': repository,
            'git_hash': self.request.get('end_git_hash'),
        })
        commits = change.Commit.CommitRange(c1, c2)
        commits = [
            change.Commit(repository, c['commit']).AsDict() for c in commits
        ]
        return [c1.AsDict()] + commits
      except request.RequestError as e:
        raise api_request_handler.BadRequestError(str(e))
