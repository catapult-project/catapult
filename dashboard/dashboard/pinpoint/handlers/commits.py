# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

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
      repository = flask_request.args.get('repository', 'chromium')
      # crbug/1363418: workaround when start_git_hash is 'undefined'
      start_git_hash = flask_request.args.get('start_git_hash')
      if start_git_hash == 'undefined':
        logging.warning(
            'start_git_hash has "undefined" as the value. Using "HEAD" as default.'
        )
        start_git_hash = 'HEAD'
      c1 = change.Commit.FromDict({
          'repository': repository,
          'git_hash': start_git_hash,
      })
      c2 = change.Commit.FromDict({
          'repository': repository,
          'git_hash': flask_request.args.get('end_git_hash'),
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
