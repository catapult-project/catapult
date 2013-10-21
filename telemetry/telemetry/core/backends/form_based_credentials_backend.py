# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from telemetry.core import util


def _WaitForLoginFormToLoad(backend, login_form_id, tab):
  def IsFormLoadedOrAlreadyLoggedIn():
    return (tab.EvaluateJavaScript(
        'document.querySelector("#%s")!== null' % login_form_id) or
            backend.IsAlreadyLoggedIn(tab))

  # Wait until the form is submitted and the page completes loading.
  util.WaitFor(IsFormLoadedOrAlreadyLoggedIn, 60)

def _SubmitFormAndWait(form_id, tab):
  tab.ExecuteJavaScript(
      'document.getElementById("%s").submit();' % form_id)

  def FinishedLoading():
    return not tab.EvaluateJavaScript(
        'document.querySelector("#%s") !== null' % form_id)

  # Wait until the form is submitted and the page completes loading.
  util.WaitFor(FinishedLoading, 60)

class FormBasedCredentialsBackend(object):
  def __init__(self):
    self._logged_in = False

  def IsAlreadyLoggedIn(self, tab):
    raise NotImplementedError()

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
  def login_input_id(self):
    raise NotImplementedError()

  @property
  def password_input_id(self):
    raise NotImplementedError()

  def IsLoggedIn(self):
    return self._logged_in

  def _ResetLoggedInState(self):
    """Makes the backend think we're not logged in even though we are.
    Should only be used in unit tests to simulate --dont-override-profile.
    """
    self._logged_in = False

  def LoginNeeded(self, tab, config):
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
      _WaitForLoginFormToLoad(self, self.login_form_id, tab)

      if self.IsAlreadyLoggedIn(tab):
        self._logged_in = True
        return True

      tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()
      logging.info('Loaded page: %s', url)

      email_id = 'document.querySelector("#%s").%s.value = "%s"; ' % (
          self.login_form_id, self.login_input_id, config['username'])
      password = 'document.querySelector("#%s").%s.value = "%s"; ' % (
          self.login_form_id, self.password_input_id, config['password'])
      tab.ExecuteJavaScript(email_id)
      tab.ExecuteJavaScript(password)

      _SubmitFormAndWait(self.login_form_id, tab)

      self._logged_in = True
      return True
    except util.TimeoutException:
      logging.warning('Timed out while loading: %s', url)
      return False

  def LoginNoLongerNeeded(self, tab): # pylint: disable=W0613
    assert self._logged_in
