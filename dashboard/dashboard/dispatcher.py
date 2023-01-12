# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Dispatches requests to request handler classes."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import pickle
pickle.HIGHEST_PROTOCOL = 2

import six
import logging

from dashboard import add_histograms
from dashboard import add_histograms_queue
from dashboard import add_point
from dashboard import add_point_queue
from dashboard import alert_groups
from dashboard import alerts
from dashboard import associate_alerts
from dashboard import buildbucket_job_status
from dashboard import edit_anomalies
from dashboard import edit_site_config
from dashboard import file_bug
from dashboard import graph_csv
from dashboard import graph_json
from dashboard import graph_revisions
from dashboard import group_report
from dashboard import layered_cache_delete_expired
from dashboard import list_tests
from dashboard import main
from dashboard import migrate_test_names
from dashboard import migrate_test_names_tasks
from dashboard import mark_recovered_alerts
from dashboard import navbar
from dashboard import pinpoint_request
from dashboard import report
from dashboard import sheriff_config_poller
from dashboard import short_uri
from dashboard import update_dashboard_stats
from dashboard import update_test_suites
from dashboard import update_test_suite_descriptors
from dashboard import uploads_info
from dashboard.api import alerts as api_alerts
from dashboard.api import config
from dashboard.api import describe
from dashboard.api import test_suites
from dashboard.api import timeseries2

if six.PY3:
  import google.cloud.logging
  from dashboard.common import datastore_hooks  # pylint: disable=ungrouped-imports

  google.cloud.logging.Client().setup_logging(log_level=logging.DEBUG)
  logging.getLogger("urllib3").setLevel(logging.INFO)
  datastore_hooks.InstallHooks()

  try:
    import googleclouddebugger
    googleclouddebugger.enable(breakpoint_enable_canary=True)
  except ImportError:
    pass

from flask import Flask
flask_app = Flask(__name__)

if six.PY3:
  from google.appengine.api import wrap_wsgi_app
  flask_app.wsgi_app = wrap_wsgi_app(flask_app.wsgi_app, use_deferred=True)


# TODO(crbug/1393102): Handler for partial traffic from fyi. Will remove.
@flask_app.route('/add_histograms_flask', methods=['POST'])
def AddHistogramsFlaskPost():
  return add_histograms.AddHistogramsPost()


@flask_app.route('/add_histograms', methods=['POST'])
def AddHistogramsPost():
  return add_histograms.AddHistogramsPost()


# TODO(crbug/1393102): Handler for partial traffic from fyi. Will remove.
@flask_app.route('/add_histograms_flask/process', methods=['POST'])
def AddHistogramsFlaskProcessPost():
  return add_histograms.AddHistogramsProcessPost()


@flask_app.route('/add_histograms/process', methods=['POST'])
def AddHistogramsProcessPost():
  return add_histograms.AddHistogramsProcessPost()


# TODO(crbug/1393102): Handler for partial traffic from fyi. Will remove.
@flask_app.route('/add_histograms_queue_flask', methods=['GET', 'POST'])
def AddHistogramsQueueFlaskPost():
  return add_histograms_queue.AddHistogramsQueuePost()


@flask_app.route('/add_histograms_queue', methods=['GET', 'POST'])
def AddHistogramsQueuePost():
  return add_histograms_queue.AddHistogramsQueuePost()


# Handler for testing partial traffic from fyi. Will remove.
@flask_app.route('/add_point_flask', methods=['POST'])
def AddPointFlaskPost():
  return add_point.AddPointPost()


@flask_app.route('/add_point', methods=['POST'])
def AddPointPost():
  return add_point.AddPointPost()


@flask_app.route('/add_point_queue', methods=['GET', 'POST'])
def AddPointQueuePost():
  return add_point_queue.AddPointQueuePost()


@flask_app.route('/alert_groups_update')
def AlertGroupsGet():
  return alert_groups.AlertGroupsGet()


@flask_app.route('/alerts', methods=['GET'])
def AlertsHandlerGet():
  return alerts.AlertsHandlerGet()


@flask_app.route('/alerts', methods=['POST'])
def AlertsHandlerPost():
  return alerts.AlertsHandlerPost()


@flask_app.route('/associate_alerts', methods=['GET', 'POST'])
def AssociateAlertsHandlerPost():
  return associate_alerts.AssociateAlertsHandlerPost()


@flask_app.route('/api/alerts', methods=['POST', 'OPTIONS'])
def AlertsPost():
  return api_alerts.AlertsPost()


@flask_app.route('/api/config', methods=['POST'])
def ConfigHandlerPost():
  return config.ConfigHandlerPost()


@flask_app.route('/api/describe', methods=['POST', 'OPTIONS'])
def DescribePost():
  return describe.DescribePost()


@flask_app.route('/api/test_suites', methods=['POST', 'OPTIONS'])
def TestSuitesPost():
  return test_suites.TestSuitesPost()


@flask_app.route('/api/timeseries2', methods=['POST'])
def TimeSeries2Post():
  return timeseries2.TimeSeries2Post()


@flask_app.route('/buildbucket_job_status/<job_id>')
def BuildbucketJobStatusGet(job_id):
  return buildbucket_job_status.BuildbucketJobStatusGet(job_id)


@flask_app.route('/delete_expired_entities')
def LayeredCacheDeleteExpiredGet():
  return layered_cache_delete_expired.LayeredCacheDeleteExpiredGet()


@flask_app.route('/edit_anomalies', methods=['POST'])
def EditAnomaliesPost():
  return edit_anomalies.EditAnomaliesPost()


@flask_app.route('/edit_site_config', methods=['GET'])
def EditSiteConfigHandlerGet():
  return edit_site_config.EditSiteConfigHandlerGet()


@flask_app.route('/edit_site_config', methods=['POST'])
def EditSiteConfigHandlerPost():
  return edit_site_config.EditSiteConfigHandlerPost()


@flask_app.route('/file_bug', methods=['GET', 'POST'])
def FileBugHandlerGet():
  return file_bug.FileBugHandlerGet()


@flask_app.route('/graph_csv', methods=['GET'])
def GraphCSVHandlerGet():
  return graph_csv.GraphCSVGet()


@flask_app.route('/graph_csv', methods=['POST'])
def GraphCSVHandlerPost():
  return graph_csv.GraphCSVPost()


@flask_app.route('/graph_json', methods=['POST'])
def GraphJsonPost():
  return graph_json.GraphJsonPost()


@flask_app.route('/graph_revisions', methods=['POST'])
def GraphRevisionsPost():
  return graph_revisions.GraphRevisionsPost()


@flask_app.route('/group_report', methods=['GET'])
def GroupReportGet():
  return group_report.GroupReportGet()


@flask_app.route('/group_report', methods=['POST'])
def GroupReportPost():
  return group_report.GroupReportPost()


@flask_app.route('/list_tests', methods=['POST'])
def ListTestsHandlerPost():
  return list_tests.ListTestsHandlerPost()


@flask_app.route('/')
def MainHandlerGet():
  return main.MainHandlerGet()


@flask_app.route('/mark_recovered_alerts', methods=['POST'])
def MarkRecoveredAlertsPost():
  return mark_recovered_alerts.MarkRecoveredAlertsPost()


@flask_app.route('/migrate_test_names', methods=['GET'])
def MigrateTestNamesGet():
  return migrate_test_names.MigrateTestNamesGet()


@flask_app.route('/migrate_test_names', methods=['POST'])
def MigrateTestNamesPost():
  return migrate_test_names.MigrateTestNamesPost()


@flask_app.route('/migrate_test_names_tasks', methods=['POST'])
def MigrateTestNamesTasksPost():
  return migrate_test_names_tasks.MigrateTestNamesTasksPost()


@flask_app.route('/navbar', methods=['POST'])
def NavbarHandlerPost():
  return navbar.NavbarHandlerPost()


@flask_app.route('/pinpoint/new/bisect', methods=['POST'])
def PinpointNewBisectPost():
  return pinpoint_request.PinpointNewBisectPost()


@flask_app.route('/pinpoint/new/perf_try', methods=['POST'])
def PinpointNewPerfTryPost():
  return pinpoint_request.PinpointNewPerfTryPost()


@flask_app.route('/pinpoint/new/prefill', methods=['POST'])
def PinpointNewPrefillPost():
  return pinpoint_request.PinpointNewPrefillPost()


@flask_app.route('/configs/update')
def SheriffConfigPollerGet():
  return sheriff_config_poller.SheriffConfigPollerGet()


@flask_app.route('/report', methods=['GET'])
def ReportHandlerGet():
  return report.ReportHandlerGet()


@flask_app.route('/report', methods=['POST'])
def ReportHandlerPost():
  return report.ReportHandlerPost()


@flask_app.route('/short_uri', methods=['GET'])
def ShortUriHandlerGet():
  return short_uri.ShortUriHandlerGet()


@flask_app.route('/short_uri', methods=['POST'])
def ShortUriHandlerPost():
  return short_uri.ShortUriHandlerPost()


@flask_app.route('/update_dashboard_stats')
def UpdateDashboardStatsGet():
  return update_dashboard_stats.UpdateDashboardStatsGet()


@flask_app.route('/update_test_suites', methods=['GET','POST'])
def UpdateTestSuitesPost():
  return update_test_suites.UpdateTestSuitesPost()


@flask_app.route('/update_test_suite_descriptors', methods=['GET', 'POST'])
def UpdateTestSuitesDescriptorsPost():
  return update_test_suite_descriptors.UpdateTestSuiteDescriptorsPost()


@flask_app.route('/uploads/<token_id>')
def UploadsInfoGet(token_id):
  return uploads_info.UploadsInfoGet(token_id)


if six.PY2:
  import webapp2

  # pylint: disable=ungrouped-imports
  from dashboard import bug_details
  from dashboard import create_health_report
  from dashboard import dump_graph_json
  from dashboard import get_diagnostics
  from dashboard import get_histogram
  from dashboard import load_from_prod
  from dashboard import put_entities_task
  from dashboard import speed_releasing
  from dashboard.api import bugs
  from dashboard.api import list_timeseries
  from dashboard.api import new_bug
  from dashboard.api import new_pinpoint
  from dashboard.api import existing_bug
  from dashboard.api import nudge_alert
  from dashboard.api import report_generate
  from dashboard.api import report_names
  from dashboard.api import report_template
  from dashboard.api import timeseries

  _URL_MAPPING = [
      ('/add_histograms', add_histograms.AddHistogramsHandler),
      ('/add_histograms/process', add_histograms.AddHistogramsProcessHandler),
      ('/add_histograms_queue', add_histograms_queue.AddHistogramsQueueHandler),
      ('/add_point', add_point.AddPointHandler),
      ('/add_point_queue', add_point_queue.AddPointQueueHandler),
      ('/alerts', alerts.AlertsHandler),
      (r'/api/alerts', api_alerts.AlertsHandler),
      (r'/api/bugs/p/(.+)/(.+)', bugs.BugsWithProjectHandler),
      (r'/api/bugs/(.*)', bugs.BugsHandler),
      (r'/api/config', config.ConfigHandler),
      (r'/api/describe', describe.DescribeHandler),
      (r'/api/list_timeseries/(.*)', list_timeseries.ListTimeseriesHandler),
      (r'/api/new_bug', new_bug.NewBugHandler),
      (r'/api/new_pinpoint', new_pinpoint.NewPinpointHandler),
      (r'/api/existing_bug', existing_bug.ExistingBugHandler),
      (r'/api/nudge_alert', nudge_alert.NudgeAlertHandler),
      (r'/api/report/generate', report_generate.ReportGenerateHandler),
      (r'/api/report/names', report_names.ReportNamesHandler),
      (r'/api/report/template', report_template.ReportTemplateHandler),
      (r'/api/test_suites', test_suites.TestSuitesHandler),
      (r'/api/timeseries/(.*)', timeseries.TimeseriesHandler),
      (r'/api/timeseries2', timeseries2.Timeseries2Handler),
      ('/associate_alerts', associate_alerts.AssociateAlertsHandler),
      ('/alert_groups_update', alert_groups.AlertGroupsHandler),
      ('/bug_details', bug_details.BugDetailsHandler),
      (r'/buildbucket_job_status/(\d+)',
       buildbucket_job_status.BuildbucketJobStatusHandler),
      ('/create_health_report', create_health_report.CreateHealthReportHandler),
      ('/configs/update', sheriff_config_poller.ConfigsUpdateHandler),
      ('/delete_expired_entities',
       layered_cache_delete_expired.LayeredCacheDeleteExpiredHandler),
      ('/dump_graph_json', dump_graph_json.DumpGraphJsonHandler),
      ('/edit_anomalies', edit_anomalies.EditAnomaliesHandler),
      ('/edit_site_config', edit_site_config.EditSiteConfigHandler),
      ('/file_bug', file_bug.FileBugHandler),
      ('/get_diagnostics', get_diagnostics.GetDiagnosticsHandler),
      ('/get_histogram', get_histogram.GetHistogramHandler),
      ('/graph_csv', graph_csv.GraphCsvHandler),
      ('/graph_json', graph_json.GraphJsonHandler),
      ('/graph_revisions', graph_revisions.GraphRevisionsHandler),
      ('/group_report', group_report.GroupReportHandler),
      ('/list_tests', list_tests.ListTestsHandler),
      ('/load_from_prod', load_from_prod.LoadFromProdHandler),
      ('/', main.MainHandler),
      ('/mark_recovered_alerts',
       mark_recovered_alerts.MarkRecoveredAlertsHandler),
      ('/migrate_test_names', migrate_test_names.MigrateTestNamesHandler),
      ('/migrate_test_names_tasks',
       migrate_test_names_tasks.MigrateTestNamesTasksHandler),
      ('/navbar', navbar.NavbarHandler),
      ('/pinpoint/new/bisect',
       pinpoint_request.PinpointNewBisectRequestHandler),
      ('/pinpoint/new/perf_try',
       pinpoint_request.PinpointNewPerfTryRequestHandler),
      ('/pinpoint/new/prefill',
       pinpoint_request.PinpointNewPrefillRequestHandler),
      ('/put_entities_task', put_entities_task.PutEntitiesTaskHandler),
      ('/report', report.ReportHandler),
      ('/short_uri', short_uri.ShortUriHandler),
      (r'/speed_releasing/(.*)', speed_releasing.SpeedReleasingHandler),
      ('/speed_releasing', speed_releasing.SpeedReleasingHandler),
      ('/update_dashboard_stats',
       update_dashboard_stats.UpdateDashboardStatsHandler),
      ('/update_test_suites', update_test_suites.UpdateTestSuitesHandler),
      ('/update_test_suite_descriptors',
       update_test_suite_descriptors.UpdateTestSuiteDescriptorsHandler),
      ('/uploads/(.+)', uploads_info.UploadInfoHandler)
  ]

  webapp2_app = webapp2.WSGIApplication(_URL_MAPPING, debug=False)

# After a handler is migrated to flask, add its handled url here.
# The listed values will be used as *prefix* to match and redirect
# the incoming requests.
_PATHS_HANDLED_BY_FLASK = [
    '/alert_groups_update',
    '/add_histograms',
    '/add_histograms_flask',
    '/add_histograms/process',
    '/add_histograms_flask/process',
    '/add_histograms_queue',
    'add_histograms_queue_flask',
    '/add_point',
    '/add_point_flask',
    '/add_point_queue',
    '/alerts',
    '/api/alerts',
    '/api/config',
    '/api/describe',
    '/api/test_suites',
    '/api/timeseries2',
    '/associate_alerts',
    '/buildbucket_job_status',
    '/configs/update',
    '/delete_expired_entities',
    '/edit_anomalies',
    '/edit_site_config',
    '/file_bug',
    '/graph_csv',
    '/graph_json',
    '/graph_revisions',
    '/group_report',
    '/list_tests',
    '/migrate_test_names',
    '/mark_recovered_alerts',
    '/navbar',
    '/pinpoint/new/bisect',
    '/pinpoint/new/perf_try',
    '/pinpoint/new/prefill',
    '/report',
    '/short_uri',
    '/update_dashboard_stats',
    '/update_test_suites',
    '/update_test_suite_descriptors',
    '/uploads',
]


def IsPathHandledByFlask(path):
  # the main hanlder cannot use startswith(). Full match here.
  if path == '/':
    return True
  return any(path.startswith(p) for p in _PATHS_HANDLED_BY_FLASK)


def APP(environ, request):
  path = environ.get('PATH_INFO', '')
  method = environ.get('REQUEST_METHOD', '')
  logging.info('Request path from environ: %s. Method: %s', path, method)

  if IsPathHandledByFlask(path) or six.PY3:
    logging.debug('Handled by flask. Python 3? %s', six.PY3)
    return flask_app(environ, request)

  logging.debug('Handled by webapp2')
  return webapp2_app(environ, request)
