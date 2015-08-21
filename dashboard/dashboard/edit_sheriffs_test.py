# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from google.appengine.api import users

from dashboard import edit_config_handler
from dashboard import edit_sheriffs
from dashboard import put_entities_task
from dashboard import testing_common
from dashboard import utils
from dashboard import xsrf
from dashboard.models import graph_data
from dashboard.models import sheriff


class EditSheriffsTest(testing_common.TestCase):

  def setUp(self):
    super(EditSheriffsTest, self).setUp()
    app = webapp2.WSGIApplication(
        [
            ('/edit_sheriffs', edit_sheriffs.EditSheriffsHandler),
            ('/put_entities_task', put_entities_task.PutEntitiesTaskHandler),
        ])
    self.testapp = webtest.TestApp(app)
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def _AddSampleTestData(self):
    """Adds some sample data used in the tests below."""
    master = graph_data.Master(id='TheMaster').put()
    bot = graph_data.Bot(id='TheBot', parent=master).put()
    suite1 = graph_data.Test(id='Suite1', parent=bot).put()
    suite2 = graph_data.Test(id='Suite2', parent=bot).put()
    graph_data.Test(id='aaa', parent=suite1, has_rows=True).put()
    graph_data.Test(id='bbb', parent=suite1, has_rows=True).put()
    graph_data.Test(id='ccc', parent=suite2, has_rows=True).put()
    graph_data.Test(id='ddd', parent=suite2, has_rows=True).put()

  def _AddSheriff(self, name, email=None, url=None,
                  internal_only=False, summarize=False, patterns=None,
                  stoppage_alert_delay=0):
    """Adds a Sheriff entity to the datastore."""
    sheriff.Sheriff(
        id=name, email=email, url=url, internal_only=internal_only,
        summarize=summarize, patterns=patterns or [],
        stoppage_alert_delay=stoppage_alert_delay).put()

  def testPost_AddNewSheriff(self):
    self.testapp.post('/edit_sheriffs', {
        'add-edit': 'add',
        'add-name': 'New Sheriff',
        'email': 'foo@chromium.org',
        'internal-only': 'true',
        'summarize': 'true',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    sheriffs = sheriff.Sheriff.query().fetch()
    self.assertEqual(1, len(sheriffs))
    self.assertEqual('New Sheriff', sheriffs[0].key.string_id())
    self.assertEqual('foo@chromium.org', sheriffs[0].email)
    self.assertEqual([], sheriffs[0].patterns)
    self.assertTrue(sheriffs[0].internal_only)
    self.assertTrue(sheriffs[0].summarize)

  def testPost_EditExistingSheriff(self):
    self._AddSampleTestData()
    self._AddSheriff('Old Sheriff')
    self.testapp.post('/edit_sheriffs', {
        'add-edit': 'edit',
        'edit-name': 'Old Sheriff',
        'email': 'bar@chromium.org',
        'url': 'http://perf.com/mysheriff',
        'internal-only': 'false',
        'summarize': 'true',
        'patterns': '*/*/Suite1/*\n',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    sheriff_entity = sheriff.Sheriff.query().fetch()[0]
    self.assertEqual('bar@chromium.org', sheriff_entity.email)
    self.assertEqual('http://perf.com/mysheriff', sheriff_entity.url)
    self.assertEqual(['*/*/Suite1/*'], sheriff_entity.patterns)
    self.assertTrue(sheriff_entity.summarize)

    # After the tasks get executed, the Test entities should also be updated.
    self.ExecuteTaskQueueTasks(
        '/put_entities_task', edit_config_handler._TASK_QUEUE_NAME)
    aaa = utils.TestKey('TheMaster/TheBot/Suite1/aaa').get()
    bbb = utils.TestKey('TheMaster/TheBot/Suite1/bbb').get()
    ccc = utils.TestKey('TheMaster/TheBot/Suite2/ccc').get()
    ddd = utils.TestKey('TheMaster/TheBot/Suite2/ddd').get()
    self.assertEqual(sheriff_entity.key, aaa.sheriff)
    self.assertEqual(sheriff_entity.key, bbb.sheriff)
    self.assertIsNone(ccc.sheriff)
    self.assertIsNone(ddd.sheriff)

  def testEditSheriff_EditPatternsList(self):
    self._AddSampleTestData()
    self._AddSheriff('Sheriff', patterns=['*/*/*/*'])
    self.testapp.post('/edit_sheriffs', {
        'add-edit': 'edit',
        'edit-name': 'Sheriff',
        'patterns': '*/*/*/ddd\n\n*/*/*/ccc',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    sheriff_entity = sheriff.Sheriff.query().fetch()[0]
    self.assertEqual(['*/*/*/ccc', '*/*/*/ddd'], sheriff_entity.patterns)

    # After the tasks get executed, the Test entities should also be updated.
    self.ExecuteTaskQueueTasks(
        '/put_entities_task', edit_config_handler._TASK_QUEUE_NAME)
    aaa = utils.TestKey('TheMaster/TheBot/Suite1/aaa').get()
    bbb = utils.TestKey('TheMaster/TheBot/Suite1/bbb').get()
    ccc = utils.TestKey('TheMaster/TheBot/Suite2/ccc').get()
    ddd = utils.TestKey('TheMaster/TheBot/Suite2/ddd').get()
    self.assertIsNone(aaa.sheriff)
    self.assertIsNone(bbb.sheriff)
    self.assertEqual(sheriff_entity.key, ccc.sheriff)
    self.assertEqual(sheriff_entity.key, ddd.sheriff)

  def testPost_EditSheriffWithNoXSRFToken_NoChangeIsMade(self):
    self._AddSheriff('Sheriff', patterns=['*/*/*'])
    self.testapp.post('/edit_sheriffs', {
        'add-edit': 'edit',
        'edit-name': 'Sheriff',
        'patterns': 'x/y/z\n\na/b/c',
    }, status=403)
    # The sheriff is unchanged.
    sheriff_entity = sheriff.Sheriff.query().fetch()[0]
    self.assertEqual(['*/*/*'], sheriff_entity.patterns)

  def testPost_WithInvalidAddEditParameter_ShowsErrorMessage(self):
    response = self.testapp.post('/edit_sheriffs', {
        'add-edit': '',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    expected_message = 'Invalid value'
    self.assertIn(expected_message, response.body)

  def testPost_NoNameGivenWhenAddingSheriff_ShowsErrorMessage(self):
    response = self.testapp.post('/edit_sheriffs', {
        'add-edit': 'add',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    expected_message = 'No name given'
    self.assertIn(expected_message, response.body)

  def testPost_NoNameGivenWhenEditingSheriff_ShowsErrorMessage(self):
    response = self.testapp.post('/edit_sheriffs', {
        'add-edit': 'edit',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    expected_message = 'No name given'
    self.assertIn(expected_message, response.body)

  def testPost_NameForNewSheriffAlreadyUsed_ShowsErrorMessage(self):
    self._AddSheriff('X')
    response = self.testapp.post('/edit_sheriffs', {
        'add-edit': 'add',
        'add-name': 'X',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    expected_message = 'already exists'
    self.assertIn(expected_message, response.body)

  def testPost_NameForExistingSheriffNotFound_ShowsErrorMessage(self):
    response = self.testapp.post('/edit_sheriffs', {
        'add-edit': 'edit',
        'edit-name': 'X',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    expected_message = 'does not exist'
    self.assertIn(expected_message, response.body)

  def testGet_SheriffDataIsEmbeddedOnPage(self):
    self._AddSheriff('Foo Sheriff', email='foo@x.org', patterns=['*/*/*/*'])
    self._AddSheriff('Bar Sheriff', summarize=True, stoppage_alert_delay=5,
                     patterns=['x/y/z', 'a/b/c'])
    response = self.testapp.get('/edit_sheriffs')
    expected = {
        'Foo Sheriff': {
            'url': '',
            'email': 'foo@x.org',
            'internal_only': False,
            'summarize': False,
            'stoppage_alert_delay': 0,
            'patterns': '*/*/*/*',
        },
        'Bar Sheriff': {
            'url': '',
            'email': '',
            'internal_only': False,
            'summarize': True,
            'stoppage_alert_delay': 5,
            'patterns': 'a/b/c\nx/y/z',
        },
    }
    actual = self.GetEmbeddedVariable(response, 'SHERIFF_DATA')
    self.assertEqual(expected, actual)


if __name__ == '__main__':
  unittest.main()
