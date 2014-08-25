# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from telemetry.core import util


class FormBasedCredentialsBackend(object):
  def __init__(self):
    self._logged_in = False

  def IsAlreadyLoggedIn(self, tab):
    return tab.EvaluateJavaScript(self.logged_in_javascript)

  @property
  def credentials_type(self):
    raise NotImplementedError()

  @property
  def url(self):
    raise NotImplementedError()

  @property
  def login_form_id(self):
    raise NotImplementedError()

  @property
  def login_button_javascript(self):
    """Some sites have custom JS to log in."""
    return None

  @property
  def login_input_id(self):
    raise NotImplementedError()

  @property
  def password_input_id(self):
    raise NotImplementedError()

  @property
  def logged_in_javascript(self):
    """Evaluates to true iff already logged in."""
    raise NotImplementedError()

  def IsLoggedIn(self):
    return self._logged_in

  def _ResetLoggedInState(self):
    """Makes the backend think we're not logged in even though we are.
    Should only be used in unit tests to simulate --dont-override-profile.
    """
    self._logged_in = False

  def _WaitForLoginState(self, action_runner):
    """Waits until it can detect either the login form, or already logged in."""
    condition = '(document.querySelector("#%s") !== null) || (%s)' % (
        self.login_form_id, self.logged_in_javascript)
    action_runner.WaitForJavaScriptCondition(condition, 60)

  def _SubmitLoginFormAndWait(self, action_runner, tab, username, password):
    """Submits the login form and waits for the navigation."""
    tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()
    email_id = 'document.querySelector("#%s #%s").value = "%s"; ' % (
        self.login_form_id, self.login_input_id, username)
    password = 'document.querySelector("#%s #%s").value = "%s"; ' % (
        self.login_form_id, self.password_input_id, password)
    tab.ExecuteJavaScript(email_id)
    tab.ExecuteJavaScript(password)
    if self.login_button_javascript:
      tab.ExecuteJavaScript(self.login_button_javascript)
    else:
      tab.ExecuteJavaScript(
          'document.getElementById("%s").submit();' % self.login_form_id)
    # Wait for the form element to disappear as confirmation of the navigation.
    action_runner.WaitForNavigate()


  def LoginNeeded(self, tab, action_runner, config):
    """Logs in to a test account.

    Raises:
      RuntimeError: if could not get credential information.
    """
    if self._logged_in:
      return True

    if 'username' not in config or 'password' not in config:
      message = ('Credentials for "%s" must include username and password.' %
                 self.credentials_type)
      raise RuntimeError(message)

    logging.debug('Logging into %s account...' % self.credentials_type)

    if 'url' in config:
      url = config['url']
    else:
      url = self.url

    try:
      logging.info('Loading %s...', url)
      tab.Navigate(url)
      self._WaitForLoginState(action_runner)

      if self.IsAlreadyLoggedIn(tab):
        self._logged_in = True
        return True

      self._SubmitLoginFormAndWait(
          action_runner, tab, config['username'], config['password'])

      self._logged_in = True
      return True
    except util.TimeoutException:
      logging.warning('Timed out while loading: %s', url)
      return False

  def LoginNoLongerNeeded(self, tab): # pylint: disable=W0613
    assert self._logged_in
