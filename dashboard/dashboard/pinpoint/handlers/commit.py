# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import six

from dashboard.api import api_request_handler
from dashboard.pinpoint.models import change
from dashboard.common import utils

if utils.IsRunningFlask():
  from flask import request

  def _CheckUser():
    pass

  # TODO(https://crbug.com/1262292): raise directly after Python2 trybots retire.
  # pylint: disable=inconsistent-return-statements
  @api_request_handler.RequestHandlerDecoratorFactory(_CheckUser)
  def CommitHandlerPost():
    repository = utils.SanitizeArgs(
        args=request.args, key_name='repository', default='chromium')
    git_hash = utils.SanitizeArgs(
        args=request.args, key_name='git_hash', default='HEAD')
    try:
      c = change.Commit.FromDict({
          'repository': repository,
          'git_hash': git_hash,
      })
      return c.AsDict()
    except KeyError as e:
      six.raise_from(
          api_request_handler.BadRequestError('Unknown git hash: %s' %
                                              git_hash), e)
else:
  class Commit(api_request_handler.ApiRequestHandler):
    # pylint: disable=abstract-method

    def _CheckUser(self):
      pass

    # TODO(https://crbug.com/1262292): raise directly after Python2 trybots retire.
    # pylint: disable=inconsistent-return-statements
    def Post(self, *args, **kwargs):
      del args, kwargs  # Unused.
      repository = self.request.get('repository', 'chromium')
      git_hash = self.request.get('git_hash')
      try:
        c = change.Commit.FromDict({
            'repository': repository,
            'git_hash': git_hash,
        })
        return c.AsDict()
      except KeyError as e:
        six.raise_from(
            api_request_handler.BadRequestError('Unknown git hash: %s' %
                                                git_hash), e)
