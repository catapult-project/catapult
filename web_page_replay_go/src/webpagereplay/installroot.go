// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package webpagereplay

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

func getCAName() string {
	return "wpr-local"
}
func getDbPath() string {
	return "sql:" + filepath.Join(os.Getenv("HOME"), ".pki/nssdb")
}

// TODO: Implement root CA installation for platforms other than Linux.
func InstallRoot(derBytes []byte) error {
	if runtime.GOOS != "linux" {
		fmt.Printf("Root certificate is skipped for %s\n", runtime.GOOS)
		return nil
	}
	CAName := getCAName()
	dbPath := getDbPath()

	fmt.Printf("Attempting to install root certificate in %q\n", dbPath)

	RemoveRoot()
	cmd := exec.Command("certutil", "-d", dbPath, "-A", "-n", CAName, "-t", "C,p,p")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return err
	}
	if err := cmd.Start(); err != nil {
		return err
	}
	if _, err := stdin.Write(derBytes); err != nil {
		return err
	}
	stdin.Close()
	if err := cmd.Wait(); err != nil {
		return fmt.Errorf("NSS certutil failed: %s\n", err)
	}

	fmt.Println("Root certificate should now be installed for NSS (i.e. Chrome).")
	return err
}

func RemoveRoot() {
	if runtime.GOOS != "linux" {
		fmt.Printf("Root certificate is skipped for %s\n", runtime.GOOS)
		return
	}
	fmt.Println("Removing root certificate from NSS (i.e. Chrome).")
	// Try to delete any existing certificate. We ignore failures since the
	// root might not yet exist.
	cmd := exec.Command("certutil", "-d", getDbPath(), "-D", "-n", getCAName())
	cmd.Run()
}
