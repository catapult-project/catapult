# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to list externally-visible Bots."""

from google.appengine.ext import ndb

from dashboard import request_handler
from dashboard import xsrf

WHITELIST_KEY = 'bot_whitelist'


class BotWhitelist(ndb.Model):
  bots = ndb.StringProperty(repeated=True)


class BotWhitelistHandler(request_handler.RequestHandler):
  """URL endpoint to view/edit the external Bot whitelist for /add_point."""

  def get(self):
    """Lists the Bots in the whitelist."""
    bots = []
    whitelist = ndb.Key('BotWhitelist', WHITELIST_KEY).get()
    if whitelist:
      bots = whitelist.bots
    self.RenderHtml('bot_whitelist.html', {'bot_whitelist': '\n'.join(bots)})

  @xsrf.TokenRequired
  def post(self):
    """Updates the Bot names in the whitelist."""
    bots = []
    whitelist_text = self.request.get('bot_whitelist', '')
    if whitelist_text:
      bots = whitelist_text.strip().split()
    whitelist = BotWhitelist.get_or_insert(WHITELIST_KEY)
    whitelist.bots = bots
    whitelist.put()
    self.RenderHtml('result.html', {
        'headline': 'Updated Bot Whitelist',
        'results': [{
            'name': 'New Bot Whitelist',
            'class': 'results-pre',
            'value': '\n'.join(bots)}]})
