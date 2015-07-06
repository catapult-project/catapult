# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to allow buildbot slaves to post data to the dashboard."""

from google.appengine.ext import ndb

from dashboard import request_handler
from dashboard import xsrf

WHITELIST_KEY = 'ip_whitelist'


class IpWhitelist(ndb.Model):
  ips = ndb.StringProperty(repeated=True)


class IpWhitelistHandler(request_handler.RequestHandler):
  """URL endpoint to view/edit the IP whitelist for /add_point."""

  def get(self):
    """Lists the IP addresses in the whitelist."""
    ips = []
    whitelist = ndb.Key('IpWhitelist', WHITELIST_KEY).get()
    if whitelist:
      ips = whitelist.ips
    self.RenderHtml('ip_whitelist.html', {'ip_whitelist': '\n'.join(ips)})

  @xsrf.TokenRequired
  def post(self):
    """Updates the IP addresses in the whitelist."""
    ips = []
    whitelist_text = self.request.get('ip_whitelist', '')
    if whitelist_text:
      ips = whitelist_text.strip().split()
    whitelist = IpWhitelist.get_or_insert(WHITELIST_KEY)
    whitelist.ips = ips
    whitelist.put()
    self.RenderHtml('result.html', {
        'headline': 'Updated IP Whitelist',
        'results': [{
            'name': 'New IP Whitelist',
            'class': 'results-pre',
            'value': '\n'.join(ips)}]})
