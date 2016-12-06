# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from functools import partial
import logging
import json

from telemetry.core import exceptions
from telemetry.internal.browser import web_contents

import py_utils


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

  def _GaiaWebviewContext(self):
    webview_contexts = self.GetWebviewContexts()
    if webview_contexts:
      return webview_contexts[0]
    return None

  def _ExecuteOobeApi(self, api, *args):
    logging.info('Invoking %s' % api)
    self.WaitForJavaScriptExpression("typeof Oobe == 'function'", 120)

    # TODO(catapult:#3028): Fix interpolation of JavaScript values.
    if self.EvaluateJavaScript("typeof %s == 'undefined'" % api):
      raise exceptions.LoginException('%s js api missing' % api)

    # Example values:
    #   |api|:          'doLogin'
    #   |args|:         ['username', 'pass', True]
    #   js:             '{}({},{},{})'
    #   js.format(...): 'doLogin("username","pass",true)'
    js = '{}(' + ('{},' * len(args)).rstrip(',') + ')'
    # TODO(catapult:#3028): Fix interpolation of JavaScript values.
    self.ExecuteJavaScript(js.format(api, *map(json.dumps, args)))

  def NavigateGuestLogin(self):
    """Logs in as guest."""
    self._ExecuteOobeApi('Oobe.guestLoginForTesting')

  def NavigateFakeLogin(self, username, password, gaia_id,
                        enterprise_enroll=False):
    """Fake user login."""
    self._ExecuteOobeApi('Oobe.loginForTesting', username, password, gaia_id,
                         enterprise_enroll)

  def NavigateGaiaLogin(self, username, password,
                        enterprise_enroll=False,
                        for_user_triggered_enrollment=False):
    """Logs in using the GAIA webview or IFrame, whichever is
    present. |enterprise_enroll| allows for enterprise enrollment.
    |for_user_triggered_enrollment| should be False for remora enrollment."""
    self._ExecuteOobeApi('Oobe.skipToLoginForTesting')
    if for_user_triggered_enrollment:
      self._ExecuteOobeApi('Oobe.switchToEnterpriseEnrollmentForTesting')

    self._NavigateGaiaLogin(username, password, enterprise_enroll)

    if enterprise_enroll:
      self.WaitForJavaScriptExpression('Oobe.isEnrollmentSuccessfulForTest()',
                                       30)
      self._ExecuteOobeApi('Oobe.enterpriseEnrollmentDone')

  def _NavigateGaiaLogin(self, username, password, enterprise_enroll):
    """Invokes NavigateIFrameLogin or NavigateWebViewLogin as appropriate."""
    def _GetGaiaFunction():
      if self._GaiaWebviewContext() is not None:
        return partial(Oobe._NavigateWebViewLogin,
                       wait_for_close=not enterprise_enroll)
      elif self._GaiaIFrameContext() is not None:
        return partial(Oobe._NavigateIFrameLogin,
                       add_user_for_testing=not enterprise_enroll)
      return None
    py_utils.WaitFor(_GetGaiaFunction, 20)(self, username, password)

  def _NavigateIFrameLogin(self, username, password, add_user_for_testing):
    """Logs into the IFrame-based GAIA screen"""
    gaia_iframe_context = py_utils.WaitFor(self._GaiaIFrameContext, timeout=30)

    if add_user_for_testing:
      self._ExecuteOobeApi('Oobe.showAddUserForTesting')
    # TODO(catapult:#3028): Fix interpolation of JavaScript values.
    self.ExecuteJavaScriptInContext("""
        document.getElementById('Email').value='%s';
        document.getElementById('Passwd').value='%s';
        document.getElementById('signIn').click();"""
            % (username, password),
        gaia_iframe_context)

  def _NavigateWebViewLogin(self, username, password, wait_for_close):
    """Logs into the webview-based GAIA screen"""
    self._NavigateWebViewEntry('identifierId', username, 'identifierNext')
    self._NavigateWebViewEntry('password', password, 'passwordNext')
    if wait_for_close:
      py_utils.WaitFor(lambda: not self._GaiaWebviewContext(), 60)

  def _NavigateWebViewEntry(self, field, value, nextField):
    self._WaitForField(field)
    self._WaitForField(nextField)
    gaia_webview_context = self._GaiaWebviewContext()
    # TODO(catapult:#3028): Fix interpolation of JavaScript values.
    gaia_webview_context.EvaluateJavaScript("""
       document.getElementById('%s').value='%s';
       document.getElementById('%s').click()"""
           % (field, value, nextField))

  def _WaitForField(self, field_id):
    gaia_webview_context = py_utils.WaitFor(self._GaiaWebviewContext, 5)
    py_utils.WaitFor(gaia_webview_context.HasReachedQuiescence, 20)
    # TODO(catapult:#3028): Fix interpolation of JavaScript values.
    gaia_webview_context.WaitForJavaScriptExpression(
        "document.getElementById('%s') != null" % field_id, 20)
