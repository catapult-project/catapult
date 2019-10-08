# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A helper request handler for request handlers that receive data."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from dashboard.common import request_handler
from dashboard.common import utils


class PostDataHandler(request_handler.RequestHandler):
  """Helper class to handle common functionality for dealing with slaves."""

  def post(self):
    # This used to just call the _CheckIpAgainstWhitelist() function, and
    # subclasses are expected now to call that function directly if they need
    # it.
    raise NotImplementedError('Handlers must implement this method!')

  def _CheckIpAgainstWhitelist(self):
    """Checks the remote address of the request against the IP whitelist.

    Returns:
      True if whitelisted, False otherwise.
    """
    whitelist = utils.GetIpWhitelist()
    if not whitelist or self.request.remote_addr in whitelist:
      return True
    # Try to log some info about the post data that is not whitelisted.
    # This could be totally bogus data, so ignore huge postdata and swallow
    # exceptions.
    try:
      data_param = self.request.get('data')
      if data_param and len(data_param) < 10000:
        # Log the start of the data; it may give clues about who is sending
        # the data and who to contact.
        logging.warn('Received data: %s...', data_param[:200])
    except Exception:  # pylint: disable=broad-except
      pass
    return False
