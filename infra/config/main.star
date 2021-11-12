#!/usr/bin/env lucicfg
# Copyright 2021 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""LUCI project configuration catapult.

After modifying this file execute it ('./main.star') to regenerate the configs.
This is also enforced by PRESUBMIT.py script.
"""

lucicfg.check_version("1.24.2", "Please update depot_tools")

# Enable LUCI Realms support.
lucicfg.enable_experiment("crbug.com/1085650")
luci.builder.defaults.experiments.set({"luci.use_realms": 100})

lucicfg.config(
    config_dir = "generated",
    fail_on_warnings = True,
    lint_checks = ["default"],
)

luci.project(
    name = "catapult",
    buildbucket = "cr-buildbucket.appspot.com",
    logdog = "luci-logdog.appspot.com",
    swarming = "chromium-swarm.appspot.com",
    acls = [
        # Publicly readable.
        acl.entry(
            roles = [
                acl.BUILDBUCKET_READER,
                acl.LOGDOG_READER,
                acl.PROJECT_CONFIGS_READER,
            ],
            groups = "all",
        ),
        acl.entry(
            roles = [
                acl.CQ_COMMITTER,
            ],
            groups = "project-catapult-committers",
        ),
        acl.entry(
            roles = [
                acl.BUILDBUCKET_TRIGGERER,
            ],
            groups = [
                "project-chromium-tryjob-access",
                "service-account-cq",  # TODO: use project-scoped account
            ],
        ),
        acl.entry(
            roles = acl.CQ_DRY_RUNNER,
            groups = "project-chromium-tryjob-access",
        ),
        acl.entry(
            roles = acl.LOGDOG_WRITER,
            groups = "luci-logdog-chromium-writers",
        ),
    ],
    bindings = [
        luci.binding(
            roles = "role/configs.validator",
            users = "catapult-try-builder@chops-service-accounts.iam.gserviceaccount.com",
        ),
    ],
)

# Per-service tweaks.
luci.logdog(gs_bucket = "chromium-luci-logdog")

luci.bucket(name = "try")

# Allow LED users to trigger swarming tasks directly when debugging try
# builders.
luci.binding(
    realm = "try",
    roles = "role/swarming.taskTriggerer",
    groups = "flex-try-led-users",
)

luci.cq(
    status_host = "chromium-cq-status.appspot.com",
    submit_max_burst = 4,
    submit_burst_delay = 480 * time.second,
)

luci.cq_group(
    name = "catapult",
    watch = cq.refset(
        repo = "https://chromium.googlesource.com/catapult",
        refs = ["refs/heads/.+"],
    ),
    retry_config = cq.retry_config(
        single_quota = 1,
        global_quota = 2,
        failure_weight = 1,
        transient_failure_weight = 1,
        timeout_weight = 2,
    ),
)

# Matches any file under the 'dashboard' root directory.
DASHBOARD_RE = ".+[+]/dashboard/.+"

def try_builder(
        name,
        os,
        is_dashboard = False,
        is_presubmit = False,
        experiment = None,
        properties = None,
        dimensions = None):
    """
    Declares a new builder in the 'try' bucket.

    Args:
      name: The name of this builder.
      os: The swarming `os` dimension.
      is_dashboard: True if this only processes
        the 'dashboard' portion of catapult.
      is_presubmit: True if this runs PRESUBMIT.
      experiment: Value 0-100 for the cq experiment %.
      properties: {key: value} dictionary for extra properties.
      dimensions: {key: value} dictionary for extra dimensions.
    """

    # TODO: switch to bbagent, delete $kitchen property
    props = {
        "$kitchen": {"devshell": True, "git_auth": True},
    }
    if properties:
        props.update(properties)

    dims = {
        "pool": "luci.flex.try",
        "os": os,
    }
    if dimensions:
        dims.update(dimensions)
    if os == "Ubuntu":
        dims["cpu"] = "x86-64"

    executable = luci.recipe(
        name = "catapult",
        cipd_package = "infra/recipe_bundles/chromium.googlesource.com/chromium/tools/build",
    )
    if is_presubmit:
        executable = luci.recipe(
            name = "run_presubmit",
            cipd_package = "infra/recipe_bundles/chromium.googlesource.com/chromium/tools/build",
        )
        props["repo_name"] = "catapult"
    if is_dashboard:
        props["dashboard_only"] = True

    luci.builder(
        name = name,
        bucket = "try",
        executable = executable,
        build_numbers = True,
        dimensions = dims,
        execution_timeout = 2 * time.hour,
        service_account = "catapult-try-builder@chops-service-accounts.iam.gserviceaccount.com",
        properties = props,
    )

    verifier_kwargs = {}

    # Presubmit sees all changes
    if not is_presubmit:
        if not is_dashboard:
            verifier_kwargs["location_regexp_exclude"] = [DASHBOARD_RE]
    if experiment != None:
        verifier_kwargs["experiment_percentage"] = experiment

    luci.cq_tryjob_verifier(
        builder = name,
        cq_group = "catapult",
        disable_reuse = is_presubmit,
        **verifier_kwargs
    )

try_builder("Catapult Linux Tryserver", "Ubuntu", properties = {"use_python3": True})
try_builder("Catapult Linux Tryserver Py2", "Ubuntu")

try_builder("Catapult Windows Tryserver Py2", "Windows-10")
try_builder("Catapult Windows Tryserver", "Windows-10", properties = {"use_python3": True})
try_builder("Catapult Win 7 Tryserver", "Windows-7", experiment = 100, properties = {"use_python3": True})

try_builder("Catapult Mac Tryserver Py2", "Mac")
try_builder("Catapult Mac Tryserver", "Mac", properties = {"use_python3": True})

try_builder("Catapult Android Tryserver", "Android", dimensions = {"device_type": "bullhead"}, properties = {"platform": "android", "use_python3": True})
try_builder("Catapult Android Tryserver Py2", "Android", dimensions = {"device_type": "bullhead"}, properties = {"platform": "android"})

try_builder("Catapult Presubmit", "Ubuntu", is_presubmit = True)

try_builder("Dashboard Linux Tryserver", "Ubuntu", is_dashboard = True)
