# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Dispatches requests to request handler classes."""

import webapp2

from dashboard import add_point
from dashboard import add_point_queue
from dashboard import alerts
from dashboard import associate_alerts
from dashboard import auto_bisect
from dashboard import auto_triage
from dashboard import bad_bisect
from dashboard import bisect_stats
from dashboard import bisect_fyi
from dashboard import buildbucket_job_status
from dashboard import can_bisect
from dashboard import change_internal_only
from dashboard import debug_alert
from dashboard import dump_graph_json
from dashboard import edit_anomalies
from dashboard import edit_anomaly_configs
from dashboard import edit_bug_labels
from dashboard import edit_sheriffs
from dashboard import edit_site_config
from dashboard import edit_test_owners
from dashboard import email_summary
from dashboard import file_bug
from dashboard import get_logs
from dashboard import graph_csv
from dashboard import graph_json
from dashboard import graph_revisions
from dashboard import group_report
from dashboard import layered_cache
from dashboard import list_monitored_tests
from dashboard import list_tests
from dashboard import load_from_prod
from dashboard import main
from dashboard import migrate_test_names
from dashboard import mr
from dashboard import navbar
from dashboard import new_points
from dashboard import oauth2_decorator
from dashboard import post_bisect_results
from dashboard import put_entities_task
from dashboard import report
from dashboard import send_stoppage_alert_emails
from dashboard import set_warning_message
from dashboard import short_uri
from dashboard import start_try_job
from dashboard import stats
from dashboard import test_buildbucket
from dashboard import update_bug_with_results
from dashboard import update_test_suites


_URL_MAPPING = [
    ('/add_point', add_point.AddPointHandler),
    ('/add_point_queue', add_point_queue.AddPointQueueHandler),
    ('/alerts', alerts.AlertsHandler),
    ('/associate_alerts', associate_alerts.AssociateAlertsHandler),
    ('/auto_bisect', auto_bisect.AutoBisectHandler),
    ('/auto_triage', auto_triage.AutoTriageHandler),
    ('/bad_bisect', bad_bisect.BadBisectHandler),
    ('/bisect_fyi', bisect_fyi.BisectFYIHandler),
    ('/bisect_stats', bisect_stats.BisectStatsHandler),
    (r'/buildbucket_job_status/(\d+)',
     buildbucket_job_status.BuildbucketJobStatusHandler),
    ('/can_bisect', can_bisect.CanBisectHandler),
    ('/change_internal_only', change_internal_only.ChangeInternalOnlyHandler),
    ('/debug_alert', debug_alert.DebugAlertHandler),
    ('/delete_expired_entities', layered_cache.DeleteExpiredEntitiesHandler),
    ('/dump_graph_json', dump_graph_json.DumpGraphJsonHandler),
    ('/edit_anomalies', edit_anomalies.EditAnomaliesHandler),
    ('/edit_anomaly_configs', edit_anomaly_configs.EditAnomalyConfigsHandler),
    ('/edit_bug_labels', edit_bug_labels.EditBugLabelsHandler),
    ('/edit_sheriffs', edit_sheriffs.EditSheriffsHandler),
    ('/edit_site_config', edit_site_config.EditSiteConfigHandler),
    ('/edit_test_owners', edit_test_owners.EditTestOwnersHandler),
    ('/email_summary', email_summary.EmailSummaryHandler),
    ('/file_bug', file_bug.FileBugHandler),
    ('/get_logs', get_logs.GetLogsHandler),
    ('/graph_csv', graph_csv.GraphCsvHandler),
    ('/graph_json', graph_json.GraphJsonHandler),
    ('/graph_revisions', graph_revisions.GraphRevisionsHandler),
    ('/group_report', group_report.GroupReportHandler),
    ('/list_monitored_tests', list_monitored_tests.ListMonitoredTestsHandler),
    ('/list_tests', list_tests.ListTestsHandler),
    ('/load_from_prod', load_from_prod.LoadFromProdHandler),
    ('/', main.MainHandler),
    ('/migrate_test_names', migrate_test_names.MigrateTestNamesHandler),
    ('/mr_deprecate_tests', mr.MRDeprecateTestsHandler),
    ('/navbar', navbar.NavbarHandler),
    ('/new_points', new_points.NewPointsHandler),
    ('/post_bisect_results', post_bisect_results.PostBisectResultsHandler),
    ('/put_entities_task', put_entities_task.PutEntitiesTaskHandler),
    ('/report', report.ReportHandler),
    ('/send_stoppage_alert_emails',
     send_stoppage_alert_emails.SendStoppageAlertEmailsHandler),
    ('/set_warning_message', set_warning_message.SetWarningMessageHandler),
    ('/short_uri', short_uri.ShortUriHandler),
    ('/start_try_job', start_try_job.StartBisectHandler),
    ('/stats_around_revision', stats.StatsAroundRevisionHandler),
    ('/stats_for_alerts', stats.StatsForAlertsHandler),
    ('/stats', stats.StatsHandler),
    ('/test_buildbucket', test_buildbucket.TestBuildbucketHandler),
    ('/update_bug_with_results',
     update_bug_with_results.UpdateBugWithResultsHandler),
    ('/update_test_suites', update_test_suites.UpdateTestSuitesHandler),
    (oauth2_decorator.DECORATOR.callback_path,
     oauth2_decorator.DECORATOR.callback_handler())
]

APP = webapp2.WSGIApplication(_URL_MAPPING, debug=False)
