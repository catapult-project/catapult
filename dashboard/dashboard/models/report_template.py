# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dashboard.common import report_query
from dashboard.common import timing
from dashboard.common import utils
from dashboard.models import internal_only_model


class ReportTemplate(internal_only_model.InternalOnlyModel):
  internal_only = ndb.BooleanProperty(indexed=True, default=False)
  name = ndb.StringProperty()
  modified = ndb.DateTimeProperty(indexed=False, auto_now=True)
  owners = ndb.StringProperty(repeated=True)
  template = ndb.JsonProperty()


STATIC_TEMPLATES = []


def ListStaticTemplates():
  return [handler for handler in STATIC_TEMPLATES
          if (not handler.template.internal_only) or utils.IsInternalUser()]


def Static(internal_only, template_id, name, modified):
  def Decorator(handler):
    handler.template = ReportTemplate(
        internal_only=internal_only,
        id=template_id,
        name=name,
        modified=modified)
    STATIC_TEMPLATES.append(handler)
    return handler
  return Decorator


def List():
  with timing.WallTimeLogger('List'), timing.CpuTimeLogger('List'):
    templates = ReportTemplate.query().fetch()
    templates += [handler.template for handler in ListStaticTemplates()]
    templates = [
        {
            'id': template.key.id(),
            'name': template.name,
            'modified': template.modified.isoformat(),
        }
        for template in templates]
    return sorted(templates, key=lambda d: d['name'])


def PutTemplate(template_id, name, owners, template):
  email = utils.GetEmail()
  if email is None:
    raise ValueError
  if template_id is None:
    if any(name == existing['name'] for existing in List()):
      raise ValueError
    entity = ReportTemplate()
  else:
    for handler in STATIC_TEMPLATES:
      if handler.template.key.id() == template_id:
        raise ValueError
    try:
      entity = ndb.Key('ReportTemplate', template_id).get()
    except AssertionError:
      # InternalOnlyModel._post_get_hook asserts that the user can access the
      # entity.
      raise ValueError
    if not entity or email not in entity.owners:
      raise ValueError
    if any(name == existing['name']
           for existing in List() if existing['id'] != template_id):
      raise ValueError

  entity.internal_only = _GetInternalOnly(template)
  entity.name = name
  entity.owners = owners
  entity.template = template
  entity.put()


def _GetInternalOnly(template):
  futures = []
  for table_row in template['rows']:
    for desc in report_query.TableRowDescriptors(table_row):
      for test_path in desc.ToTestPathsSync():
        futures.append(utils.TestMetadataKey(test_path).get_async())
      desc.statistic = 'avg'
      for test_path in desc.ToTestPathsSync():
        futures.append(utils.TestMetadataKey(test_path).get_async())
  ndb.Future.wait_all(futures)
  tests = [future.get_result() for future in futures]
  return any(test.internal_only for test in tests if test)


def GetReport(template_id, revisions):
  with timing.WallTimeLogger('GetReport'), timing.CpuTimeLogger('GetReport'):
    try:
      template = ndb.Key('ReportTemplate', template_id).get()
    except AssertionError:
      # InternalOnlyModel._post_get_hook asserts that the user can access the
      # entity.
      return None

    result = {'editable': False}
    if template:
      result['owners'] = template.owners
      result['editable'] = utils.GetEmail() in template.owners
      result['report'] = report_query.ReportQuery(
          template.template, revisions).FetchSync()
    else:
      for handler in ListStaticTemplates():
        if handler.template.key.id() != template_id:
          continue
        template = handler.template
        report = handler(revisions)
        if isinstance(report, report_query.ReportQuery):
          report = report.FetchSync()
        result['report'] = report
        break
      if template is None:
        return None

    result['id'] = template.key.id()
    result['name'] = template.name
    result['internal'] = template.internal_only
    return result


def TestKeysForReportTemplate(template_id):
  template = ndb.Key('ReportTemplate', int(template_id)).get()
  if not template:
    return

  for table_row in template.template['rows']:
    for desc in report_query.TableRowDescriptors(table_row):
      for test_path in desc.ToTestPathsSync():
        yield utils.TestMetadataKey(test_path)
        yield utils.OldStyleTestKey(test_path)
