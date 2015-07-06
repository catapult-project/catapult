# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Contains a utility function to check whitelist IPs."""

from google.appengine.ext import ndb

from dashboard import ip_whitelist


def CheckWhiteListedIp(ip_address):
  """Checks if the given IP address is whitelisted.

  Args:
    ip_address: The IP address given by the user.

  Returns:
    Whether the IP address is whitelisted or not.
  """
  whitelist = _GetIpWhiteList()
  if not whitelist:
    return False
  if ip_address in whitelist.ips:
    return True
  else:
    return False


def _GetIpWhiteList():
  """Gets the IpWhitelist entity."""
  return ndb.Key('IpWhitelist', ip_whitelist.WHITELIST_KEY).get()
