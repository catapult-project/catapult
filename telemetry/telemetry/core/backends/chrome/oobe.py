# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core import web_contents


class Oobe(web_contents.WebContents):
  def __init__(self, inspector_backend):
    super(Oobe, self).__init__(inspector_backend)

  def _GaiaIFrameContext(self):
    max_context_id = self.EnableAllContexts()
    logging.debug('%d contexts in Gaia page' % max_context_id)
    for gaia_iframe_context in range(max_context_id + 1):
      try:
        if self.EvaluateJavaScriptInContext(
            "document.readyState == 'complete' && "
            "document.getElementById('Email') != null",
            gaia_iframe_context):
          return gaia_iframe_context
      except exceptions.EvaluateException:
        pass
    return None

  def _GaiaWebViewContext(self):
    devtools_context_map = (
        self._inspector_backend._devtools_client.GetUpdatedInspectableContexts()
    )
    for context in devtools_context_map.contexts:
      if context['type'] == 'webview':
        return web_contents.WebContents(
            devtools_context_map.GetInspectorBackend(context['id']))
    return None

  def _ExecuteOobeApi(self, api, *args):
    logging.info('Invoking %s' % api)
    self.WaitForJavaScriptExpression("typeof Oobe == 'function'", 20)

    if self.EvaluateJavaScript("typeof %s == 'undefined'" % api):
      raise exceptions.LoginException('%s js api missing' % api)

    js = api + '(' + ("'%s'," * len(args)).rstrip(',') + ');'
    self.ExecuteJavaScript(js % args)

  def NavigateGuestLogin(self):
    """Logs in as guest."""
    self._ExecuteOobeApi('Oobe.guestLoginForTesting')

  def NavigateFakeLogin(self, username, password):
    """Fake user login."""
    self._ExecuteOobeApi('Oobe.loginForTesting', username, password)

  def NavigateEnterpriseEnrollment(self, username, password):
    """Enterprise enrolls using the GAIA webview or IFrame, whichever
    is present."""
    self._ExecuteOobeApi('Oobe.skipToLoginForTesting')
    self._ExecuteOobeApi('Oobe.switchToEnterpriseEnrollmentForTesting')
    if self._GaiaIFrameContext() is None:
      self._NavigateWebViewLogin(username, password, wait_for_close=False)
    else:
      self._NavigateIFrameLogin(username, password)

    # TODO(resetswitch): Move UI specifics out of this util. crbug/486904
    self.WaitForJavaScriptExpression("""
        document.getElementById('oauth-enrollment').classList.contains(
            'oauth-enroll-state-success')""", 30)
    self._ExecuteOobeApi('Oobe.enterpriseEnrollmentDone')

  def NavigateGaiaLogin(self, username, password):
    """Logs in using the GAIA webview or IFrame, whichever is
    present."""
    def _GetGaiaFunction():
      self._ExecuteOobeApi('Oobe.showAddUserForTesting')
      if self._GaiaIFrameContext() is not None:
        return Oobe._NavigateIFrameLogin
      elif self._GaiaWebViewContext() is not None:
        return Oobe._NavigateWebViewLogin
      return None
    util.WaitFor(_GetGaiaFunction, 20)(self, username, password)

  def _NavigateIFrameLogin(self, username, password):
    """Logs into the IFrame-based GAIA screen"""
    gaia_iframe_context = util.WaitFor(self._GaiaIFrameContext, timeout=30)

    self.ExecuteJavaScriptInContext("""
        document.getElementById('Email').value='%s';
        document.getElementById('Passwd').value='%s';
        document.getElementById('signIn').click();"""
            % (username, password),
        gaia_iframe_context)

  def _NavigateWebViewLogin(self, username, password, wait_for_close=True):
    """Logs into the webview-based GAIA screen"""
    self._NavigateWebViewEntry('identifierId', username)
    self._GaiaWebViewContext().WaitForJavaScriptExpression(
        "document.getElementById('identifierId') == null", 20)
    self._NavigateWebViewEntry('password', password)
    if wait_for_close:
      util.WaitFor(lambda: self._GaiaWebViewContext() == None, 20)

  def _NavigateWebViewEntry(self, field, value):
    self._WaitForField(field)
    self._WaitForField('next')
    gaia_webview_context = self._GaiaWebViewContext()
    gaia_webview_context.EvaluateJavaScript("""
       document.getElementById('%s').value='%s';
       document.getElementById('next').click()"""
           % (field, value))

  def _WaitForField(self, field_id):
    gaia_webview_context = util.WaitFor(self._GaiaWebViewContext, 5)
    util.WaitFor(gaia_webview_context.HasReachedQuiescence, 20)
    gaia_webview_context.WaitForJavaScriptExpression(
        "document.getElementById('%s') != null" % field_id, 20)
