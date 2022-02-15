# -*- coding: utf-8 -*-
# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Integration tests for the iam command."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

from collections import defaultdict
import json

from gslib.exception import CommandException
from gslib.project_id import PopulateProjectId
import gslib.tests.testcase as testcase
from gslib.tests.testcase.integration_testcase import SkipForS3
from gslib.tests.testcase.integration_testcase import SkipForXML
from gslib.tests.util import GenerationFromURI as urigen
from gslib.tests.util import SetBotoConfigForTest
from gslib.tests.util import unittest
from gslib.third_party.storage_apitools import storage_v1_messages as apitools_messages
from gslib.utils.constants import UTF8
from gslib.utils.iam_helper import BindingsToDict
from gslib.utils.iam_helper import BindingStringToTuple as bstt
from gslib.utils.iam_helper import BindingsTuple
from gslib.utils.iam_helper import DiffBindings
from gslib.utils.iam_helper import IsEqualBindings
from gslib.utils.iam_helper import PatchBindings
from gslib.utils.retry_util import Retry

bvle = apitools_messages.Policy.BindingsValueListEntry

# Feature iam_bucket_roles must be turned on in bigstore dev config for setting
# the new IAM policies on buckets.
IAM_BUCKET_READ_ROLE_ABBREV = 'legacyBucketReader'
IAM_BUCKET_READ_ROLE = 'roles/storage.%s' % IAM_BUCKET_READ_ROLE_ABBREV
# GCS IAM does not currently support new object-level roles.
IAM_OBJECT_READ_ROLE = 'roles/storage.legacyObjectReader'
IAM_OBJECT_VIEWER_ROLE = 'roles/storage.objectViewer'

TEST_CONDITION_DESCRIPTION = 'Description for our test condition.'
TEST_CONDITION_EXPR_RESOURCE_IS_OBJECT = (
    'resource.type == "google.cloud.storage.Object"')
TEST_CONDITION_TITLE = 'Test Condition Title'


def gen_binding(role, members=None, condition=None):
  """Generate the "bindings" portion of an IAM Policy dictionary.

  Generates list of dicts which each represent a
  storage_v1_messages.Policy.BindingsValueListEntry object. The list will
  contain a single dict which has attributes corresponding to arguments passed
  to this method.

  Args:
    role: (str) An IAM policy role (e.g. "roles/storage.objectViewer"). Fully
        specified in BindingsValueListEntry.
    members: (List[str]) A list of members (e.g. ["user:foo@bar.com"]). If None,
        bind to ["allUsers"]. Fully specified in BindingsValueListEntry.
    condition: (Dict) A dictionary representing the JSON used to define a
        binding condition, containing the keys "description", "expression", and
        "title".

  Returns:
    (List[Dict[str, Any]]) A Python representation of the "bindings" portion of
    an IAM Policy.
  """
  binding = {
      'members': ['allUsers'] if members is None else members,
      'role': role,
  }
  if condition:
    binding['condition'] = condition
  return [binding]


class TestIamIntegration(testcase.GsUtilIntegrationTestCase):
  """Superclass for iam integration test cases."""

  def assertEqualsPoliciesString(self, a, b):
    """Asserts two serialized policy bindings are equal."""
    expected = [
        bvle(members=binding_dict['members'], role=binding_dict['role'])
        for binding_dict in json.loads(a)['bindings']
    ]
    result = [
        bvle(members=binding_dict['members'], role=binding_dict['role'])
        for binding_dict in json.loads(b)['bindings']
    ]
    self.assertTrue(IsEqualBindings(expected, result))


@SkipForS3('Tests use GS IAM model.')
@SkipForXML('XML IAM control is not supported.')
class TestIamHelpers(testcase.GsUtilUnitTestCase):
  """Unit tests for iam command helper."""

  def test_convert_bindings_simple(self):
    """Tests that Policy.bindings lists are converted to dicts properly."""
    self.assertEquals(BindingsToDict([]), defaultdict(set))
    expected = defaultdict(set, {'x': set(['y'])})
    self.assertEquals(BindingsToDict([bvle(role='x', members=['y'])]), expected)

  def test_convert_bindings_duplicates(self):
    """Test that role and member duplication are converted correctly."""
    expected = defaultdict(set, {'x': set(['y', 'z'])})
    duplicate_roles = [
        bvle(role='x', members=['y']),
        bvle(role='x', members=['z'])
    ]
    duplicate_members = [
        bvle(role='x', members=['z', 'y']),
        bvle(role='x', members=['z'])
    ]
    self.assertEquals(BindingsToDict(duplicate_roles), expected)
    self.assertEquals(BindingsToDict(duplicate_members), expected)

  def test_equality_bindings_literal(self):
    """Tests an easy case of identical bindings."""
    bindings = [bvle(role='x', members=['y'])]
    self.assertTrue(IsEqualBindings([], []))
    self.assertTrue(IsEqualBindings(bindings, bindings))

  def test_equality_bindings_extra_roles(self):
    """Tests bindings equality when duplicate roles are added."""
    bindings = [bvle(role='x', members=['x', 'y'])]
    bindings2 = bindings * 2
    bindings3 = [
        bvle(role='x', members=['y']),
        bvle(role='x', members=['x']),
    ]
    self.assertTrue(IsEqualBindings(bindings, bindings2))
    self.assertTrue(IsEqualBindings(bindings, bindings3))

  def test_diff_bindings_add_role(self):
    """Tests simple grant behavior of Policy.bindings diff."""
    expected = [bvle(role='x', members=['y'])]
    (granted, removed) = DiffBindings([], expected)
    self.assertEquals(granted.bindings, expected)
    self.assertEquals(removed.bindings, [])

  def test_diff_bindings_drop_role(self):
    """Tests simple remove behavior of Policy.bindings diff."""
    expected = [bvle(role='x', members=['y'])]
    (granted, removed) = DiffBindings(expected, [])
    self.assertEquals(granted.bindings, [])
    self.assertEquals(removed.bindings, expected)

  def test_diff_bindings_swap_role(self):
    """Tests expected behavior of switching a role."""
    old = [bvle(role='x', members=['y'])]
    new = [bvle(role='a', members=['b'])]
    (granted, removed) = DiffBindings(old, new)
    self.assertEquals(granted.bindings, new)
    self.assertEquals(removed.bindings, old)

  def test_diff_bindings_add_member(self):
    """Tests expected behavior of adding a member to a role."""
    old = [bvle(role='x', members=['y'])]
    new = [bvle(role='x', members=['z', 'y'])]
    expected = [bvle(role='x', members=['z'])]
    (granted, removed) = DiffBindings(old, new)
    self.assertEquals(granted.bindings, expected)
    self.assertEquals(removed.bindings, [])

  def test_diff_bindings_drop_member(self):
    """Tests expected behavior of dropping a member from a role."""
    old = [bvle(role='x', members=['z', 'y'])]
    new = [bvle(role='x', members=['y'])]
    expected = [bvle(role='x', members=['z'])]
    (granted, removed) = DiffBindings(old, new)
    self.assertEquals(granted.bindings, [])
    self.assertEquals(removed.bindings, expected)

  def test_diff_bindings_swap_member(self):
    """Tests expected behavior of switching a member in a role."""
    old = [bvle(role='x', members=['z'])]
    new = [bvle(role='x', members=['y'])]
    (granted, removed) = DiffBindings(old, new)
    self.assertEquals(granted.bindings, new)
    self.assertEquals(removed.bindings, old)

  def test_patch_bindings_grant(self):
    """Tests patching a grant binding."""
    base = [
        bvle(role='a', members=['user:foo@bar.com']),
        bvle(role='b', members=['user:foo@bar.com']),
        bvle(role='c', members=['user:foo@bar.com']),
    ]
    diff = [
        bvle(role='d', members=['user:foo@bar.com']),
    ]
    expected = base + diff
    res = PatchBindings(base, BindingsTuple(True, diff))
    self.assertTrue(IsEqualBindings(res, expected))

  def test_patch_bindings_remove(self):
    """Tests patching a remove binding."""
    base = [
        bvle(members=['user:foo@bar.com'], role='a'),
        bvle(members=['user:foo@bar.com'], role='b'),
        bvle(members=['user:foo@bar.com'], role='c'),
    ]
    diff = [
        bvle(members=['user:foo@bar.com'], role='a'),
    ]
    expected = [
        bvle(members=['user:foo@bar.com'], role='b'),
        bvle(members=['user:foo@bar.com'], role='c'),
    ]

    res = PatchBindings(base, BindingsTuple(False, diff))
    self.assertTrue(IsEqualBindings(res, expected))

  def test_patch_bindings_remove_all(self):
    """Tests removing all roles from a member."""
    base = [
        bvle(members=['user:foo@bar.com'], role='a'),
        bvle(members=['user:foo@bar.com'], role='b'),
        bvle(members=['user:foo@bar.com'], role='c'),
    ]
    diff = [
        bvle(members=['user:foo@bar.com'], role=''),
    ]
    res = PatchBindings(base, BindingsTuple(False, diff))
    self.assertEquals(res, [])

    diff = [
        bvle(members=['user:foo@bar.com'], role='a'),
        bvle(members=['user:foo@bar.com'], role='b'),
        bvle(members=['user:foo@bar.com'], role='c'),
    ]

    res = PatchBindings(base, BindingsTuple(False, diff))
    self.assertEquals(res, [])

  def test_patch_bindings_multiple_users(self):
    """Tests expected behavior when multiple users exist."""
    expected = [
        bvle(members=['user:fii@bar.com'], role='b'),
    ]
    base = [
        bvle(members=['user:foo@bar.com'], role='a'),
        bvle(members=['user:foo@bar.com', 'user:fii@bar.com'], role='b'),
        bvle(members=['user:foo@bar.com'], role='c'),
    ]
    diff = [
        bvle(members=['user:foo@bar.com'], role='a'),
        bvle(members=['user:foo@bar.com'], role='b'),
        bvle(members=['user:foo@bar.com'], role='c'),
    ]
    res = PatchBindings(base, BindingsTuple(False, diff))
    self.assertTrue(IsEqualBindings(res, expected))

  def test_patch_bindings_grant_all_users(self):
    """Tests a public member grant."""
    base = [
        bvle(role='a', members=['user:foo@bar.com']),
        bvle(role='b', members=['user:foo@bar.com']),
        bvle(role='c', members=['user:foo@bar.com']),
    ]
    diff = [
        bvle(role='a', members=['allUsers']),
    ]
    expected = [
        bvle(role='a', members=['allUsers', 'user:foo@bar.com']),
        bvle(role='b', members=['user:foo@bar.com']),
        bvle(role='c', members=['user:foo@bar.com']),
    ]

    res = PatchBindings(base, BindingsTuple(True, diff))
    self.assertTrue(IsEqualBindings(res, expected))

  def test_patch_bindings_public_member_overwrite(self):
    """Tests public member vs. public member interaction."""
    base = [
        bvle(role='a', members=['allUsers']),
    ]
    diff = [
        bvle(role='a', members=['allAuthenticatedUsers']),
    ]

    res = PatchBindings(base, BindingsTuple(True, diff))
    self.assertTrue(IsEqualBindings(res, base + diff))

  def test_valid_public_member_single_role(self):
    """Tests parsing single role (case insensitive)."""
    (_, bindings) = bstt(True, 'allusers:admin')
    self.assertEquals(len(bindings), 1)
    self.assertIn(bvle(members=['allUsers'], role='roles/storage.admin'),
                  bindings)

  def test_grant_no_role_error(self):
    """Tests that an error is raised when no role is specified for a grant."""
    with self.assertRaises(CommandException):
      bstt(True, 'allUsers')
    with self.assertRaises(CommandException):
      bstt(True, 'user:foo@bar.com')
    with self.assertRaises(CommandException):
      bstt(True, 'user:foo@bar.com:')
    with self.assertRaises(CommandException):
      bstt(True, 'deleted:user:foo@bar.com?uid=1234:')

  def test_remove_all_roles(self):
    """Tests parsing a -d allUsers or -d user:foo@bar.com request."""
    # Input specifies remove all roles from allUsers.
    (is_grant, bindings) = bstt(False, 'allUsers')
    self.assertEquals(len(bindings), 1)
    self.assertIn(bvle(members=['allUsers'], role=''), bindings)
    self.assertEquals((is_grant, bindings), bstt(False, 'allUsers:'))

    # Input specifies remove all roles from a user.
    (_, bindings) = bstt(False, 'user:foo@bar.com')
    self.assertEquals(len(bindings), 1)

  def test_valid_multiple_roles(self):
    """Tests parsing of multiple roles bound to one user."""
    (_, bindings) = bstt(True, 'allUsers:a,b,c,roles/custom')
    self.assertEquals(len(bindings), 4)
    self.assertIn(bvle(members=['allUsers'], role='roles/storage.a'), bindings)
    self.assertIn(bvle(members=['allUsers'], role='roles/storage.b'), bindings)
    self.assertIn(bvle(members=['allUsers'], role='roles/storage.c'), bindings)
    self.assertIn(bvle(members=['allUsers'], role='roles/custom'), bindings)

  def test_valid_custom_roles(self):
    """Tests parsing of custom roles bound to one user."""
    (_, bindings) = bstt(True, 'user:foo@bar.com:roles/custom1,roles/custom2')
    self.assertEquals(len(bindings), 2)
    self.assertIn(bvle(members=['user:foo@bar.com'], role='roles/custom1'),
                  bindings)
    self.assertIn(bvle(members=['user:foo@bar.com'], role='roles/custom2'),
                  bindings)

  def test_valid_member(self):
    """Tests member parsing (case insensitive)."""
    (_, bindings) = bstt(True, 'User:foo@bar.com:admin')
    self.assertEquals(len(bindings), 1)
    self.assertIn(
        bvle(members=['user:foo@bar.com'], role='roles/storage.admin'),
        bindings)

  def test_valid_deleted_member(self):
    """Tests deleted member parsing (case insensitive)."""
    (_, bindings) = bstt(False, 'Deleted:User:foo@bar.com?uid=123')
    self.assertEquals(len(bindings), 1)
    self.assertIn(bvle(members=['deleted:user:foo@bar.com?uid=123'], role=''),
                  bindings)
    (_, bindings) = bstt(True, 'deleted:User:foo@bar.com?uid=123:admin')
    self.assertEquals(len(bindings), 1)
    self.assertIn(
        bvle(members=['deleted:user:foo@bar.com?uid=123'],
             role='roles/storage.admin'), bindings)
    # These emails can actually have multiple query params
    (_, bindings) = bstt(
        True,
        'deleted:user:foo@bar.com?query=param,uid=123?uid=456:admin,admin2')
    self.assertEquals(len(bindings), 2)
    self.assertIn(
        bvle(members=['deleted:user:foo@bar.com?query=param,uid=123?uid=456'],
             role='roles/storage.admin'), bindings)
    self.assertIn(
        bvle(members=['deleted:user:foo@bar.com?query=param,uid=123?uid=456'],
             role='roles/storage.admin2'), bindings)

  def test_duplicate_roles(self):
    """Tests that duplicate roles are ignored."""
    (_, bindings) = bstt(True, 'allUsers:a,a')
    self.assertEquals(len(bindings), 1)
    self.assertIn(bvle(members=['allUsers'], role='roles/storage.a'), bindings)

  def test_invalid_input(self):
    """Tests invalid input handling."""
    with self.assertRaises(CommandException):
      bstt(True, 'non_valid_public_member:role')
    with self.assertRaises(CommandException):
      bstt(True, 'non_valid_type:id:role')
    with self.assertRaises(CommandException):
      bstt(True, 'user:r')
    with self.assertRaises(CommandException):
      bstt(True, 'projectViewer:123424:admin')
    with self.assertRaises(CommandException):
      bstt(True, 'deleted:user')
    with self.assertRaises(CommandException):
      bstt(True, 'deleted:not_a_type')
    with self.assertRaises(CommandException):
      bstt(True, 'deleted:user:foo@no_uid_suffix')

  def test_invalid_n_args(self):
    """Tests invalid input due to too many colons."""
    with self.assertRaises(CommandException):
      bstt(True, 'allUsers:some_id:some_role')
    with self.assertRaises(CommandException):
      bstt(True, 'user:foo@bar.com:r:nonsense')
    with self.assertRaises(CommandException):
      bstt(True, 'deleted:user:foo@bar.com?uid=1234:r:nonsense')


@SkipForS3('Tests use GS IAM model.')
@SkipForXML('XML IAM control is not supported.')
class TestIamCh(TestIamIntegration):
  """Integration tests for iam ch command."""

  def setUp(self):
    super(TestIamCh, self).setUp()
    self.bucket = self.CreateBucket()
    self.bucket2 = self.CreateBucket()
    self.object = self.CreateObject(bucket_uri=self.bucket, contents=b'foo')
    self.object2 = self.CreateObject(bucket_uri=self.bucket, contents=b'bar')

    self.bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                            return_stdout=True)
    self.object_iam_string = self.RunGsUtil(['iam', 'get', self.object.uri],
                                            return_stdout=True)
    self.object2_iam_string = self.RunGsUtil(['iam', 'get', self.object2.uri],
                                             return_stdout=True)

    self.user = 'user:foo@bar.com'
    self.user2 = 'user:bar@foo.com'

  def test_patch_no_role(self):
    """Tests expected failure if no bindings are listed."""
    stderr = self.RunGsUtil(['iam', 'ch', self.bucket.uri],
                            return_stderr=True,
                            expected_status=1)
    self.assertIn('CommandException', stderr)

  def test_patch_single_grant_single_bucket(self):
    """Tests granting single role."""
    self.assertHasNo(self.bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)
    self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    self.assertHas(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)

  def test_patch_repeated_grant(self):
    """Granting multiple times for the same member will have no effect."""
    self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])
    self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    self.assertHas(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)

  def test_patch_single_remove_single_bucket(self):
    """Tests removing a single role."""
    self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])
    self.RunGsUtil([
        'iam', 'ch', '-d',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    self.assertHasNo(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)

  def test_patch_null_remove(self):
    """Removing a non-existent binding will have no effect."""
    self.RunGsUtil([
        'iam', 'ch', '-d',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    self.assertHasNo(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)
    self.assertEqualsPoliciesString(bucket_iam_string, self.bucket_iam_string)

  def test_patch_mixed_grant_remove_single_bucket(self):
    """Tests that mixing grant and remove requests will succeed."""
    self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user2, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])
    self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), '-d',
        '%s:%s' % (self.user2, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    self.assertHas(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)
    self.assertHasNo(bucket_iam_string, self.user2, IAM_BUCKET_READ_ROLE)

  def test_patch_public_grant_single_bucket(self):
    """Test public grant request interacts properly with existing members."""
    self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])
    self.RunGsUtil([
        'iam', 'ch',
        'allUsers:%s' % IAM_BUCKET_READ_ROLE_ABBREV, self.bucket.uri
    ])

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    self.assertHas(bucket_iam_string, 'allUsers', IAM_BUCKET_READ_ROLE)
    self.assertHas(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)

  def test_patch_remove_all_roles(self):
    """Remove with no roles specified will remove member from all bindings."""
    self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri
    ])
    self.RunGsUtil(['iam', 'ch', '-d', self.user, self.bucket.uri])

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    self.assertHasNo(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)

  def test_patch_single_object(self):
    """Tests object IAM patch behavior."""
    self.assertHasNo(self.object_iam_string, self.user, IAM_OBJECT_READ_ROLE)
    self.RunGsUtil(
        ['iam', 'ch',
         '%s:legacyObjectReader' % self.user, self.object.uri])

    object_iam_string = self.RunGsUtil(['iam', 'get', self.object.uri],
                                       return_stdout=True)
    self.assertHas(object_iam_string, self.user, IAM_OBJECT_READ_ROLE)

  def test_patch_multithreaded_single_object(self):
    """Tests the edge-case behavior of multithreaded execution."""
    self.assertHasNo(self.object_iam_string, self.user, IAM_OBJECT_READ_ROLE)
    self.RunGsUtil([
        '-m', 'iam', 'ch',
        '%s:legacyObjectReader' % self.user, self.object.uri
    ])

    object_iam_string = self.RunGsUtil(['iam', 'get', self.object.uri],
                                       return_stdout=True)
    self.assertHas(object_iam_string, self.user, IAM_OBJECT_READ_ROLE)

  def test_patch_invalid_input(self):
    """Tests that listing bindings after a bucket will throw an error."""
    stderr = self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri,
        '%s:%s' % (self.user2, IAM_BUCKET_READ_ROLE_ABBREV)
    ],
                            return_stderr=True,
                            expected_status=1)
    self.assertIn('CommandException', stderr)

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    self.assertHas(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)
    self.assertHasNo(bucket_iam_string, self.user2, IAM_BUCKET_READ_ROLE)

  def test_patch_disallowed_binding_type(self):
    """Tests that we disallow certain binding types with appropriate err."""
    stderr = self.RunGsUtil(
        ['iam', 'ch', 'projectOwner:my-project:admin', self.bucket.uri],
        return_stderr=True,
        expected_status=1)
    self.assertIn('not supported', stderr)

  def test_patch_multiple_objects(self):
    """Tests IAM patch against multiple objects."""
    self.RunGsUtil([
        'iam', 'ch', '-r',
        '%s:legacyObjectReader' % self.user, self.bucket.uri
    ])

    object_iam_string = self.RunGsUtil(['iam', 'get', self.object.uri],
                                       return_stdout=True)
    object2_iam_string = self.RunGsUtil(['iam', 'get', self.object2.uri],
                                        return_stdout=True)
    self.assertHas(object_iam_string, self.user, IAM_OBJECT_READ_ROLE)
    self.assertHas(object2_iam_string, self.user, IAM_OBJECT_READ_ROLE)

  def test_patch_multithreaded_multiple_objects(self):
    """Tests multithreaded behavior against multiple objects."""
    self.RunGsUtil([
        '-m', 'iam', 'ch', '-r',
        '%s:legacyObjectReader' % self.user, self.bucket.uri
    ])

    object_iam_string = self.RunGsUtil(['iam', 'get', self.object.uri],
                                       return_stdout=True)
    object2_iam_string = self.RunGsUtil(['iam', 'get', self.object2.uri],
                                        return_stdout=True)
    self.assertHas(object_iam_string, self.user, IAM_OBJECT_READ_ROLE)
    self.assertHas(object2_iam_string, self.user, IAM_OBJECT_READ_ROLE)

  def test_patch_error(self):
    """See TestIamSet.test_set_error."""
    stderr = self.RunGsUtil([
        'iam', 'ch',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri,
        'gs://%s' % self.nonexistent_bucket_name, self.bucket2.uri
    ],
                            return_stderr=True,
                            expected_status=1)
    self.assertIn('BucketNotFoundException', stderr)

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    bucket2_iam_string = self.RunGsUtil(['iam', 'get', self.bucket2.uri],
                                        return_stdout=True)

    self.assertHas(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)
    self.assertEqualsPoliciesString(bucket2_iam_string, self.bucket_iam_string)

  def test_patch_force_error(self):
    """See TestIamSet.test_set_force_error."""
    stderr = self.RunGsUtil([
        'iam', 'ch', '-f',
        '%s:%s' % (self.user, IAM_BUCKET_READ_ROLE_ABBREV), self.bucket.uri,
        'gs://%s' % self.nonexistent_bucket_name, self.bucket2.uri
    ],
                            return_stderr=True,
                            expected_status=1)
    self.assertIn('CommandException', stderr)

    bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                       return_stdout=True)
    bucket2_iam_string = self.RunGsUtil(['iam', 'get', self.bucket2.uri],
                                        return_stdout=True)

    self.assertHas(bucket_iam_string, self.user, IAM_BUCKET_READ_ROLE)
    self.assertHas(bucket2_iam_string, self.user, IAM_BUCKET_READ_ROLE)

  def test_patch_multithreaded_error(self):
    """See TestIamSet.test_set_multithreaded_error."""
    # TODO(b/135780661): Remove retry after bug resolved
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      stderr = self.RunGsUtil([
          '-m', 'iam', 'ch', '-r',
          '%s:legacyObjectReader' % self.user,
          'gs://%s' % self.nonexistent_bucket_name, self.bucket.uri
      ],
                              return_stderr=True,
                              expected_status=1)
      self.assertIn('BucketNotFoundException', stderr)

    # TODO(b/135780661): Remove retry after bug resolved
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      object_iam_string = self.RunGsUtil(['iam', 'get', self.object.uri],
                                         return_stdout=True)
      object2_iam_string = self.RunGsUtil(['iam', 'get', self.object2.uri],
                                          return_stdout=True)

      self.assertEqualsPoliciesString(self.object_iam_string, object_iam_string)
      self.assertEqualsPoliciesString(self.object_iam_string,
                                      object2_iam_string)

    _Check1()
    _Check2()

  def test_assert_has(self):
    test_policy = {
        'bindings': [{
            'members': ['allUsers'],
            'role': 'roles/storage.admin'
        }, {
            'members': ['user:foo@bar.com', 'serviceAccount:bar@foo.com'],
            'role': IAM_BUCKET_READ_ROLE
        }]
    }

    self.assertHas(json.dumps(test_policy), 'allUsers', 'roles/storage.admin')
    self.assertHas(json.dumps(test_policy), 'user:foo@bar.com',
                   IAM_BUCKET_READ_ROLE)
    self.assertHasNo(json.dumps(test_policy), 'allUsers', IAM_BUCKET_READ_ROLE)
    self.assertHasNo(json.dumps(test_policy), 'user:foo@bar.com',
                     'roles/storage.admin')

  def assertHas(self, policy, member, role):
    """Asserts a member has permission for role.

    Given an IAM policy, check if the specified member is bound to the
    specified role. Does not check group inheritence -- that is, if checking
    against the [{'member': ['allUsers'], 'role': X}] policy, this function
    will still raise an exception when testing for any member other than
    'allUsers' against role X.

    This function does not invoke the TestIamPolicy endpoints to smartly check
    IAM policy resolution. This function is simply to assert the expected IAM
    policy is returned, not whether or not the IAM policy is being invoked as
    expected.

    Args:
      policy: Policy object as formatted by IamCommand._GetIam()
      member: A member string (e.g. 'user:foo@bar.com').
      role: A fully specified role (e.g. 'roles/storage.admin')

    Raises:
      AssertionError if member is not bound to role.
    """

    policy = json.loads(policy)
    bindings = dict((p['role'], p) for p in policy.get('bindings', []))
    if role in bindings:
      if member in bindings[role]['members']:
        return
    raise AssertionError('Member \'%s\' does not have permission \'%s\' in '
                         'policy %s' % (member, role, policy))

  def assertHasNo(self, policy, member, role):
    """Functions as logical compliment of TestIamCh.assertHas()."""
    try:
      self.assertHas(policy, member, role)
    except AssertionError:
      pass
    else:
      raise AssertionError('Member \'%s\' has permission \'%s\' in '
                           'policy %s' % (member, role, policy))


@SkipForS3('Tests use GS IAM model.')
@SkipForXML('XML IAM control is not supported.')
class TestIamSet(TestIamIntegration):
  """Integration tests for iam set command."""

  def _patch_binding(self, policy, role, new_policy):
    """Returns a patched Python object representation of a Policy.

    Given replaces the original role:members binding in policy with new_policy.

    Args:
      policy: Python dict representation of a Policy instance.
      role: An IAM policy role (e.g. "roles/storage.objectViewer"). Fully
            specified in BindingsValueListEntry.
      new_policy: A Python dict representation of a Policy instance, with a
                  single BindingsValueListEntry entry.

    Returns:
      A Python dict representation of the patched IAM Policy object.
    """
    bindings = [
        b for b in policy.get('bindings', []) if b.get('role', '') != role
    ]
    bindings.extend(new_policy)
    policy = dict(policy)
    policy['bindings'] = bindings
    return policy

  # TODO(iam-beta): Replace gen_binding, _patch_binding with generators from
  # iam_helper.
  def setUp(self):
    super(TestIamSet, self).setUp()

    self.public_bucket_read_binding = gen_binding(IAM_BUCKET_READ_ROLE)
    self.public_object_read_binding = gen_binding(IAM_OBJECT_READ_ROLE)
    self.project_viewer_objectviewer_with_cond_binding = gen_binding(
        IAM_OBJECT_VIEWER_ROLE,
        # Note: We use projectViewer:some-project-id here because conditions
        # cannot be applied to a binding that only has allUsers in the members
        # list; the API gives back a 400 error if you try.
        members=['projectViewer:%s' % PopulateProjectId()],
        condition={
            'title': TEST_CONDITION_TITLE,
            'description': TEST_CONDITION_DESCRIPTION,
            'expression': TEST_CONDITION_EXPR_RESOURCE_IS_OBJECT,
        })

    self.bucket = self.CreateBucket()
    self.versioned_bucket = self.CreateVersionedBucket()

    # Create a bucket to fetch its policy, used as a base for other policies.
    self.bucket_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                            return_stdout=True)
    self.old_bucket_iam_path = self.CreateTempFile(
        contents=self.bucket_iam_string.encode(UTF8))

    # Using the existing bucket's policy, make an altered policy that allows
    # allUsers to be "legacyBucketReader"s. Some tests will later apply this
    # policy.
    self.new_bucket_iam_policy = self._patch_binding(
        json.loads(self.bucket_iam_string), IAM_BUCKET_READ_ROLE,
        self.public_bucket_read_binding)
    self.new_bucket_iam_path = self.CreateTempFile(
        contents=json.dumps(self.new_bucket_iam_policy).encode(UTF8))

    # Using the existing bucket's policy, make an altered policy that contains
    # a binding with a condition in it. Some tests will later apply this policy.
    self.new_bucket_policy_with_conditions_policy = json.loads(
        self.bucket_iam_string)
    self.new_bucket_policy_with_conditions_policy['bindings'].append(
        self.project_viewer_objectviewer_with_cond_binding[0])
    self.new_bucket_policy_with_conditions_path = self.CreateTempFile(
        contents=json.dumps(self.new_bucket_policy_with_conditions_policy))

    # Create an object to fetch its policy, used as a base for other policies.
    tmp_object = self.CreateObject(contents='foobar')
    self.object_iam_string = self.RunGsUtil(['iam', 'get', tmp_object.uri],
                                            return_stdout=True)
    self.old_object_iam_path = self.CreateTempFile(
        contents=self.object_iam_string.encode(UTF8))

    # Using the existing object's policy, make an altered policy that allows
    # allUsers to be "legacyObjectReader"s. Some tests will later apply this
    # policy.
    self.new_object_iam_policy = self._patch_binding(
        json.loads(self.object_iam_string), IAM_OBJECT_READ_ROLE,
        self.public_object_read_binding)
    self.new_object_iam_path = self.CreateTempFile(
        contents=json.dumps(self.new_object_iam_policy).encode(UTF8))

  def test_seek_ahead_iam(self):
    """Ensures that the seek-ahead iterator is being used with iam commands."""

    gsutil_object = self.CreateObject(bucket_uri=self.bucket,
                                      contents=b'foobar')

    # This forces the seek-ahead iterator to be utilized.
    with SetBotoConfigForTest([('GSUtil', 'task_estimation_threshold', '1'),
                               ('GSUtil', 'task_estimation_force', 'True')]):
      stderr = self.RunGsUtil(
          ['-m', 'iam', 'set', self.new_object_iam_path, gsutil_object.uri],
          return_stderr=True)
      self.assertIn('Estimated work for this command: objects: 1\n', stderr)

  def test_set_invalid_iam_bucket(self):
    """Ensures invalid content returns error on input check."""
    # TODO(b/135780661): Remove retry after bug resolved
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      inpath = self.CreateTempFile(contents=b'badIam')
      stderr = self.RunGsUtil(['iam', 'set', inpath, self.bucket.uri],
                              return_stderr=True,
                              expected_status=1)
      self.assertIn('ArgumentException', stderr)

    # TODO(b/135780661): Remove retry after bug resolved
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Tests that setting with a non-existent file will also return error.
      stderr = self.RunGsUtil(
          ['iam', 'set', 'nonexistent/path', self.bucket.uri],
          return_stderr=True,
          expected_status=1)
      self.assertIn('ArgumentException', stderr)

    _Check1()
    _Check2()

  def test_get_invalid_bucket(self):
    """Ensures that invalid bucket names returns an error."""
    stderr = self.RunGsUtil(['iam', 'get', self.nonexistent_bucket_name],
                            return_stderr=True,
                            expected_status=1)
    self.assertIn('CommandException', stderr)

    stderr = self.RunGsUtil(
        ['iam', 'get', 'gs://%s' % self.nonexistent_bucket_name],
        return_stderr=True,
        expected_status=1)
    self.assertIn('BucketNotFoundException', stderr)

    # N.B.: The call to wildcard_iterator.WildCardIterator here will invoke
    # ListBucket, which only promises eventual consistency. We use @Retry here
    # to mitigate errors due to this.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check():  # pylint: disable=invalid-name
      # There are at least two buckets in the project
      # due to TestIamSet.setUp().
      stderr = self.RunGsUtil(['iam', 'get', 'gs://*'],
                              return_stderr=True,
                              expected_status=1)
      self.assertIn('CommandException', stderr)

    _Check()

  def test_set_valid_iam_bucket(self):
    """Tests setting a valid IAM on a bucket."""
    self.RunGsUtil(
        ['iam', 'set', '-e', '', self.new_bucket_iam_path, self.bucket.uri])
    set_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                    return_stdout=True)
    self.RunGsUtil(
        ['iam', 'set', '-e', '', self.old_bucket_iam_path, self.bucket.uri])
    reset_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                      return_stdout=True)

    self.assertEqualsPoliciesString(self.bucket_iam_string, reset_iam_string)
    self.assertIn(self.public_bucket_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

  @unittest.skip('Disabled until all projects whitelisted for conditions.')
  def test_set_and_get_valid_bucket_policy_with_conditions(self):
    """Tests setting and getting an IAM policy with conditions on a bucket."""
    self.RunGsUtil([
        'iam', 'set', '-e', '', self.new_bucket_policy_with_conditions_path,
        self.bucket.uri
    ])
    get_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                    return_stdout=True)
    self.assertIn(TEST_CONDITION_DESCRIPTION, get_iam_string)
    self.assertIn(TEST_CONDITION_EXPR_RESOURCE_IS_OBJECT,
                  get_iam_string.replace('\\', ''))
    self.assertIn(TEST_CONDITION_TITLE, get_iam_string)

  # Note: We only test this for buckets, since objects cannot currently have
  # conditions in their policy bindings.
  @unittest.skip('Disabled until all projects whitelisted for conditions.')
  def test_ch_fails_after_setting_conditions(self):
    """Tests that if we "set" a policy with conditions, "ch" won't patch it."""
    print()
    self.RunGsUtil([
        'iam', 'set', '-e', '', self.new_bucket_policy_with_conditions_path,
        self.bucket.uri
    ])

    # Assert that we get an error both with and without ch's `-f` option.
    # Without `-f`:
    stderr = self.RunGsUtil(
        ['iam', 'ch', 'allUsers:objectViewer', self.bucket.uri],
        return_stderr=True,
        expected_status=1)
    self.assertIn('CommandException: Could not patch IAM policy for', stderr)
    # Also make sure we print the workaround message.
    self.assertIn('The resource had conditions present', stderr)

    # With `-f`:
    stderr = self.RunGsUtil(
        ['iam', 'ch', '-f', 'allUsers:objectViewer', self.bucket.uri],
        return_stderr=True,
        expected_status=1)
    self.assertIn('CommandException: Some IAM policies could not be patched',
                  stderr)
    # Also make sure we print the workaround message.
    self.assertIn('Some resources had conditions', stderr)

  def test_set_blank_etag(self):
    """Tests setting blank etag behaves appropriately."""
    self.RunGsUtil(
        ['iam', 'set', '-e', '', self.new_bucket_iam_path, self.bucket.uri])

    set_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                    return_stdout=True)
    self.RunGsUtil([
        'iam', 'set', '-e',
        json.loads(set_iam_string)['etag'], self.old_bucket_iam_path,
        self.bucket.uri
    ])

    reset_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                      return_stdout=True)

    self.assertEqualsPoliciesString(self.bucket_iam_string, reset_iam_string)
    self.assertIn(self.public_bucket_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

  def test_set_valid_etag(self):
    """Tests setting valid etag behaves correctly."""
    get_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                    return_stdout=True)
    self.RunGsUtil([
        'iam', 'set', '-e',
        json.loads(get_iam_string)['etag'], self.new_bucket_iam_path,
        self.bucket.uri
    ])

    set_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                    return_stdout=True)
    self.RunGsUtil([
        'iam', 'set', '-e',
        json.loads(set_iam_string)['etag'], self.old_bucket_iam_path,
        self.bucket.uri
    ])

    reset_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                      return_stdout=True)

    self.assertEqualsPoliciesString(self.bucket_iam_string, reset_iam_string)
    self.assertIn(self.public_bucket_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

  def test_set_invalid_etag(self):
    """Tests setting an invalid etag format raises an error."""
    self.RunGsUtil(['iam', 'get', self.bucket.uri], return_stdout=True)
    stderr = self.RunGsUtil([
        'iam', 'set', '-e', 'some invalid etag', self.new_bucket_iam_path,
        self.bucket.uri
    ],
                            return_stderr=True,
                            expected_status=1)
    self.assertIn('ArgumentException', stderr)

  def test_set_mismatched_etag(self):
    """Tests setting mismatched etag raises an error."""
    get_iam_string = self.RunGsUtil(['iam', 'get', self.bucket.uri],
                                    return_stdout=True)
    self.RunGsUtil([
        'iam', 'set', '-e',
        json.loads(get_iam_string)['etag'], self.new_bucket_iam_path,
        self.bucket.uri
    ])
    stderr = self.RunGsUtil([
        'iam', 'set', '-e',
        json.loads(get_iam_string)['etag'], self.new_bucket_iam_path,
        self.bucket.uri
    ],
                            return_stderr=True,
                            expected_status=1)
    self.assertIn('PreconditionException', stderr)

  def _create_multiple_objects(self):
    """Creates two versioned objects and return references to all versions.

    Returns:
      A four-tuple (a, b, a*, b*) of storage_uri.BucketStorageUri instances.
    """

    old_gsutil_object = self.CreateObject(bucket_uri=self.versioned_bucket,
                                          contents=b'foo')
    old_gsutil_object2 = self.CreateObject(bucket_uri=self.versioned_bucket,
                                           contents=b'bar')
    gsutil_object = self.CreateObject(
        bucket_uri=self.versioned_bucket,
        object_name=old_gsutil_object.object_name,
        contents=b'new_foo',
        gs_idempotent_generation=urigen(old_gsutil_object))
    gsutil_object2 = self.CreateObject(
        bucket_uri=self.versioned_bucket,
        object_name=old_gsutil_object2.object_name,
        contents=b'new_bar',
        gs_idempotent_generation=urigen(old_gsutil_object2))
    return (old_gsutil_object, old_gsutil_object2, gsutil_object,
            gsutil_object2)

  def test_set_valid_iam_multiple_objects(self):
    """Tests setting a valid IAM on multiple objects."""
    (old_gsutil_object, old_gsutil_object2, gsutil_object,
     gsutil_object2) = self._create_multiple_objects()

    # Set IAM policy on newest versions of all objects.
    self.RunGsUtil([
        'iam', 'set', '-r', self.new_object_iam_path, self.versioned_bucket.uri
    ])
    set_iam_string = self.RunGsUtil(['iam', 'get', gsutil_object.uri],
                                    return_stdout=True)
    set_iam_string2 = self.RunGsUtil(['iam', 'get', gsutil_object2.uri],
                                     return_stdout=True)
    self.assertEqualsPoliciesString(set_iam_string, set_iam_string2)
    self.assertIn(self.public_object_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

    # Check that old versions are not affected by the set IAM call.
    iam_string_old = self.RunGsUtil(
        ['iam', 'get', old_gsutil_object.version_specific_uri],
        return_stdout=True)
    iam_string_old2 = self.RunGsUtil(
        ['iam', 'get', old_gsutil_object2.version_specific_uri],
        return_stdout=True)
    self.assertEqualsPoliciesString(iam_string_old, iam_string_old2)
    self.assertEqualsPoliciesString(self.object_iam_string, iam_string_old)

  def test_set_valid_iam_multithreaded_multiple_objects(self):
    """Tests setting a valid IAM on multiple objects."""
    (old_gsutil_object, old_gsutil_object2, gsutil_object,
     gsutil_object2) = self._create_multiple_objects()

    # Set IAM policy on newest versions of all objects.
    self.RunGsUtil([
        '-m', 'iam', 'set', '-r', self.new_object_iam_path,
        self.versioned_bucket.uri
    ])
    set_iam_string = self.RunGsUtil(['iam', 'get', gsutil_object.uri],
                                    return_stdout=True)
    set_iam_string2 = self.RunGsUtil(['iam', 'get', gsutil_object2.uri],
                                     return_stdout=True)
    self.assertEqualsPoliciesString(set_iam_string, set_iam_string2)
    self.assertIn(self.public_object_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

    # Check that old versions are not affected by the set IAM call.
    iam_string_old = self.RunGsUtil(
        ['iam', 'get', old_gsutil_object.version_specific_uri],
        return_stdout=True)
    iam_string_old2 = self.RunGsUtil(
        ['iam', 'get', old_gsutil_object2.version_specific_uri],
        return_stdout=True)
    self.assertEqualsPoliciesString(iam_string_old, iam_string_old2)
    self.assertEqualsPoliciesString(self.object_iam_string, iam_string_old)

  def test_set_valid_iam_multiple_objects_all_versions(self):
    """Tests set IAM policy on all versions of all objects."""
    (old_gsutil_object, old_gsutil_object2, gsutil_object,
     gsutil_object2) = self._create_multiple_objects()

    self.RunGsUtil([
        'iam', 'set', '-ra', self.new_object_iam_path, self.versioned_bucket.uri
    ])
    set_iam_string = self.RunGsUtil(
        ['iam', 'get', gsutil_object.version_specific_uri], return_stdout=True)
    set_iam_string2 = self.RunGsUtil(
        ['iam', 'get', gsutil_object2.version_specific_uri], return_stdout=True)
    set_iam_string_old = self.RunGsUtil(
        ['iam', 'get', old_gsutil_object.version_specific_uri],
        return_stdout=True)
    set_iam_string_old2 = self.RunGsUtil(
        ['iam', 'get', old_gsutil_object2.version_specific_uri],
        return_stdout=True)
    self.assertEqualsPoliciesString(set_iam_string, set_iam_string2)
    self.assertEqualsPoliciesString(set_iam_string, set_iam_string_old)
    self.assertEqualsPoliciesString(set_iam_string, set_iam_string_old2)
    self.assertIn(self.public_object_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

  def test_set_error(self):
    """Tests fail-fast behavior of iam set.

    We initialize two buckets (bucket, bucket2) and attempt to set both along
    with a third, non-existent bucket in between, self.nonexistent_bucket_name.

    We want to ensure
      1.) Bucket "bucket" IAM policy has been set appropriately,
      2.) Bucket self.nonexistent_bucket_name has caused an error, and
      3.) gsutil has exited and "bucket2"'s IAM policy is unaltered.
    """

    bucket = self.CreateBucket()
    bucket2 = self.CreateBucket()

    stderr = self.RunGsUtil([
        'iam', 'set', '-e', '', self.new_bucket_iam_path, bucket.uri,
        'gs://%s' % self.nonexistent_bucket_name, bucket2.uri
    ],
                            return_stderr=True,
                            expected_status=1)

    # The program has exited due to a bucket lookup 404.
    self.assertIn('BucketNotFoundException', stderr)
    set_iam_string = self.RunGsUtil(['iam', 'get', bucket.uri],
                                    return_stdout=True)
    set_iam_string2 = self.RunGsUtil(['iam', 'get', bucket2.uri],
                                     return_stdout=True)

    # The IAM policy has been set on Bucket "bucket".
    self.assertIn(self.public_bucket_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

    # The IAM policy for Bucket "bucket2" remains unchanged.
    self.assertEqualsPoliciesString(self.bucket_iam_string, set_iam_string2)

  def test_set_force_error(self):
    """Tests ignoring failure behavior of iam set.

    Similar to TestIamSet.test_set_error, except here we want to ensure
      1.) Bucket "bucket" IAM policy has been set appropriately,
      2.) Bucket self.nonexistent_bucket_name has caused an error, BUT
      3.) gsutil has continued and "bucket2"'s IAM policy has been set as well.
    """
    bucket = self.CreateBucket()
    bucket2 = self.CreateBucket()

    stderr = self.RunGsUtil([
        'iam', 'set', '-f', self.new_bucket_iam_path, bucket.uri,
        'gs://%s' % self.nonexistent_bucket_name, bucket2.uri
    ],
                            return_stderr=True,
                            expected_status=1)

    # The program asserts that an error has occured (due to 404).
    self.assertIn('CommandException', stderr)

    set_iam_string = self.RunGsUtil(['iam', 'get', bucket.uri],
                                    return_stdout=True)
    set_iam_string2 = self.RunGsUtil(['iam', 'get', bucket2.uri],
                                     return_stdout=True)

    # The IAM policy has been set appropriately on Bucket "bucket".
    self.assertIn(self.public_bucket_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

    # The IAM policy has also been set on Bucket "bucket2".
    self.assertEqualsPoliciesString(set_iam_string, set_iam_string2)

  def test_set_multithreaded_error(self):
    """Tests fail-fast behavior of multithreaded iam set.

    This is testing gsutil iam set with the -m and -r flags present in
    invocation.

    N.B.: Currently, (-m, -r) behaves identically to (-m, -fr) and (-fr,).
    However, (-m, -fr) and (-fr,) behavior is not as expected due to
    name_expansion.NameExpansionIterator.next raising problematic e.g. 404
    or 403 errors. More details on this issue can be found in comments in
    commands.iam.IamCommand._SetIam.

    Thus, the following command
      gsutil -m iam set -fr <object_policy> gs://bad_bucket gs://good_bucket

    will NOT set policies on objects in gs://good_bucket due to an error when
    iterating over gs://bad_bucket.
    """

    # TODO(b/135780661): Remove retry after bug resolved
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      stderr = self.RunGsUtil([
          '-m', 'iam', 'set', '-r', self.new_object_iam_path,
          'gs://%s' % self.nonexistent_bucket_name, self.bucket.uri
      ],
                              return_stderr=True,
                              expected_status=1)
      self.assertIn('BucketNotFoundException', stderr)

    # TODO(b/135780661): Remove retry after bug resolved
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      gsutil_object = self.CreateObject(bucket_uri=self.bucket,
                                        contents=b'foobar')
      gsutil_object2 = self.CreateObject(bucket_uri=self.bucket,
                                         contents=b'foobar')
      set_iam_string = self.RunGsUtil(['iam', 'get', gsutil_object.uri],
                                      return_stdout=True)
      set_iam_string2 = self.RunGsUtil(['iam', 'get', gsutil_object2.uri],
                                       return_stdout=True)
      self.assertEqualsPoliciesString(set_iam_string, set_iam_string2)
      self.assertEqualsPoliciesString(self.object_iam_string, set_iam_string)

    _Check1()
    _Check2()

  def test_set_valid_iam_single_unversioned_object(self):
    """Tests setting a valid IAM on an object."""
    gsutil_object = self.CreateObject(bucket_uri=self.bucket,
                                      contents=b'foobar')

    lookup_uri = gsutil_object.uri
    self.RunGsUtil(['iam', 'set', self.new_object_iam_path, lookup_uri])
    set_iam_string = self.RunGsUtil(['iam', 'get', lookup_uri],
                                    return_stdout=True)
    self.RunGsUtil([
        'iam', 'set', '-e',
        json.loads(set_iam_string)['etag'], self.old_object_iam_path, lookup_uri
    ])
    reset_iam_string = self.RunGsUtil(['iam', 'get', lookup_uri],
                                      return_stdout=True)

    self.assertEqualsPoliciesString(self.object_iam_string, reset_iam_string)
    self.assertIn(self.public_object_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

  def test_set_valid_iam_single_versioned_object(self):
    """Tests setting a valid IAM on a versioned object."""
    gsutil_object = self.CreateObject(bucket_uri=self.bucket,
                                      contents=b'foobar')

    lookup_uri = gsutil_object.version_specific_uri
    self.RunGsUtil(['iam', 'set', self.new_object_iam_path, lookup_uri])
    set_iam_string = self.RunGsUtil(['iam', 'get', lookup_uri],
                                    return_stdout=True)
    self.RunGsUtil([
        'iam', 'set', '-e',
        json.loads(set_iam_string)['etag'], self.old_object_iam_path, lookup_uri
    ])
    reset_iam_string = self.RunGsUtil(['iam', 'get', lookup_uri],
                                      return_stdout=True)

    self.assertEqualsPoliciesString(self.object_iam_string, reset_iam_string)
    self.assertIn(self.public_object_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

  def test_set_valid_iam_multithreaded_single_object(self):
    """Tests setting a valid IAM on a single object with multithreading."""
    gsutil_object = self.CreateObject(bucket_uri=self.bucket,
                                      contents=b'foobar')

    lookup_uri = gsutil_object.version_specific_uri
    self.RunGsUtil(
        ['-m', 'iam', 'set', '-e', '', self.new_object_iam_path, lookup_uri])
    set_iam_string = self.RunGsUtil(['iam', 'get', lookup_uri],
                                    return_stdout=True)
    self.RunGsUtil(
        ['-m', 'iam', 'set', '-e', '', self.old_object_iam_path, lookup_uri])
    reset_iam_string = self.RunGsUtil(['iam', 'get', lookup_uri],
                                      return_stdout=True)

    self.assertEqualsPoliciesString(self.object_iam_string, reset_iam_string)
    self.assertIn(self.public_object_read_binding[0],
                  json.loads(set_iam_string)['bindings'])

    # Test multithreading on single object, specified with wildcards.
    lookup_uri = '%s*' % self.bucket.uri
    self.RunGsUtil(
        ['-m', 'iam', 'set', '-e', '', self.new_object_iam_path, lookup_uri])
    set_iam_string = self.RunGsUtil(['iam', 'get', lookup_uri],
                                    return_stdout=True)
    self.RunGsUtil(
        ['-m', 'iam', 'set', '-e', '', self.old_object_iam_path, lookup_uri])
    reset_iam_string = self.RunGsUtil(['iam', 'get', lookup_uri],
                                      return_stdout=True)

    self.assertEqualsPoliciesString(self.object_iam_string, reset_iam_string)
    self.assertIn(self.public_object_read_binding[0],
                  json.loads(set_iam_string)['bindings'])
