# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import webapp2


class CancelPage(webapp2.RequestHandler):

  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    response = {'success': False}
    self.response.out.write(json.dumps(response))


app = webapp2.WSGIApplication([('/cloud_mapper/cancel', CancelPage)])
