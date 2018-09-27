// Copyright 2018 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package main

// [START gae_go_env_import]
import (
	"google.golang.org/appengine" // Required external App Engine library
)

// [END gae_go_env_import]
// [START gae_go_env_main]
func main() {
	appengine.Main() // Starts the server to receive requests
}

// [END gae_go_env_main]
