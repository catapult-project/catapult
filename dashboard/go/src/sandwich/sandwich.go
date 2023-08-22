// Copyright 2023 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Program sandwich re-runs a pinpoint autobisect job as a sandwich verification workflow.
// Runs in dry-run mode by default, so you need to specify -dry-run=false to get it to
// actually start the workflow.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strconv"
	"strings"

	"cloud.google.com/go/datastore"
	executions "cloud.google.com/go/workflows/executions/apiv1"
	executionspb "cloud.google.com/go/workflows/executions/apiv1/executionspb"
)

var (
	app              = flag.String("app", "chromeperf", "GAE project app name")
	location         = flag.String("location", "us-central1", "location for workflow execution")
	workflowName     = flag.String("workflow", "sandwich-verification-workflow-prod", "name of workflow to execute")
	pinpointJobIDStr = flag.String("pinpoint-job-id", "", "id of the pinpoint job")
	attemptCount     = flag.Int("attempt-count", 30, "iterations verification job will run")
	dryRun           = flag.Bool("dry-run", true, "dry run for StartWorkflow; just print CreateExecutionRequest to stdout")
	execIDStr        = flag.String("execution-id", "", "execution id of the workflow")
)

type BenchmarkArguments struct {
	Benchmark string `datastore:"benchmark"`
	Chart     string `datastore:"chart"`
	Statistic string `datastore:"statistic"`
	Story     string `datastore:"story"`
}

type PinpointJob struct {
	Arguments          []byte             `datastore:"arguments"` // base64-encoded JSON
	BenchmarkArguments BenchmarkArguments `datastore:"benchmark_arguments"`
	ComparisonMode     string             `datastore:"comparison_mode"`
	Configuration      string             `datastore:"configuration"`
}

type Stats struct {
	Lower    float64 `json:lower`
	Upper    float64 `json:upper`
	PValue   float64 `json:"p_value"`
	CtrlMed  float64 `json:"control_median"`
	TreatMed float64 `json:"treatment_median"`
}

type WorkflowResult struct {
	JobId    string `json:"job_id"`
	Decision bool   `json:"decision"`
	Stats    *Stats `json:"statistic"`
}

func exitWithError(err error) {
	fmt.Printf("error: %v\n", err)
	os.Exit(1)
}

func StartWorkflow(ctx context.Context) {
	dsClient, err := datastore.NewClient(ctx, *app)
	if err != nil {
		exitWithError(err)
	}
	defer dsClient.Close()

	pinpointJobID, err := strconv.ParseInt(*pinpointJobIDStr, 16, 64)
	pinpointJobKey := datastore.IDKey("Job", pinpointJobID, nil)
	job := &PinpointJob{}
	err = dsClient.Get(ctx, pinpointJobKey, job)
	if err != nil &&
		// struct PinpointJob is a subset of fields that are in datastore, so ignore errors about missing fields on it.
		!strings.Contains(err.Error(), "no such struct field") {
		exitWithError(err)
	}
	if job.ComparisonMode != "performance" {
		fmt.Printf("%s is not an autobisect job (its comparison_mode is '%s')\n",
			*pinpointJobIDStr, job.ComparisonMode)
		return
	}
	arguments := map[string]interface{}{}
	err = json.Unmarshal(job.Arguments, &arguments)
	if err != nil {
		exitWithError(err)
	}

	benchmark := arguments["benchmark"]
	botName := arguments["configuration"]
	story := arguments["story"]
	target := arguments["target"]
	measurement := arguments["chart"]
	startGitHash := arguments["start_git_hash"]
	endGitHash := arguments["end_git_hash"]

	executionsClient, err := executions.NewClient(ctx)
	if err != nil {
		exitWithError(err)
	}
	defer executionsClient.Close()

	workflowArgs := map[string]interface{}{
		"anomaly": map[string]interface{}{
			"benchmark":      benchmark,
			"bot_name":       botName,
			"story":          story,
			"measurement":    measurement,
			"target":         target,
			"start_git_hash": startGitHash,
			"end_git_hash":   endGitHash,
			"attempt_count":  attemptCount,
		},
	}
	encodedArgs, err := json.Marshal(workflowArgs)
	if err != nil {
		exitWithError(err)
	}

	createReq := &executionspb.CreateExecutionRequest{
		Parent: fmt.Sprintf("projects/%s/locations/%s/workflows/%s", *app, *location, *workflowName),
		Execution: &executionspb.Execution{
			Argument:     string(encodedArgs),
			CallLogLevel: executionspb.Execution_LOG_ALL_CALLS,
		},
	}
	if *dryRun {
		fmt.Printf("CreateExecutionRequest:\n%+v\n", createReq)
		return
	}
	execution, err := executionsClient.CreateExecution(ctx, createReq)
	if err != nil {
		exitWithError(err)
	}

	fmt.Printf("Workflow execution created. Check status with\n\ngo run sandwich.go -execution-id %s\n\n", execution.Name)
}

func CheckWorkflow(ctx context.Context) {
	executionsClient, err := executions.NewClient(ctx)
	if err != nil {
		exitWithError(err)
	}
	defer executionsClient.Close()

	req := &executionspb.GetExecutionRequest{
		// See https://pkg.go.dev/cloud.google.com/go/workflows/executions/apiv1beta/executionspb#GetExecutionRequest.
		Name: fmt.Sprintf("projects/%s/locations/%s/workflows/%s/executions/%s",
			*app, *location, *workflowName, *execIDStr),
	}
	resp, err := executionsClient.GetExecution(ctx, req)
	if err != nil {
		fmt.Printf("executionsClient failed to get execution %v\n", err)
	}

	if len(resp.Result) != 0 {
		result := &WorkflowResult{}
		err = json.Unmarshal([]byte(resp.Result), &result)
		if err != nil {
			exitWithError(err)
		}
		fmt.Printf("exec_id: %v verification job: %v decision: %v lower: %v upper: %v p-value %v ctrl_med %v treat_med %v \n",
			*execIDStr,
			result.JobId,
			result.Decision,
			result.Stats.Lower,
			result.Stats.Upper,
			result.Stats.PValue,
			result.Stats.CtrlMed,
			result.Stats.TreatMed,
		)
	} else {
		fmt.Printf("exec_id: %v cabe failed", *execIDStr)
	}
}

func main() {
	flag.Parse()

	ctx := context.Background()

	if *pinpointJobIDStr != "" {
		StartWorkflow(ctx)
	} else if *execIDStr != "" {
		CheckWorkflow(ctx)
	} else {
		fmt.Printf("Please provide a Pinpoint Job ID or a Workflow Execution ID")
	}

}
