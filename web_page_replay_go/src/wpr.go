// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Program wpr records and replays web traffic.
package main

import (
	"crypto/tls"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"

	"github.com/codegangsta/cli"
	"webpagereplay"
)

const longUsage = `%s [record|replay] [options] archive_file

   To record web pages:
     1. Start this program in record mode.
        $ GOPATH=$PWD go run src/wpr.go record archive.json
     2. Load the web pages you want to record in a web browser. It is important to
        clear browser caches before this so that all subresources are requested
        from the network.
     3. Kill the process to stop recording.

   To replay web pages:
     1. Start this program in replay mode with a previously recorded archive.
        $ GOPATH=$PWD go run src/wpr.go replay archive.json
     2. Load recorded pages in a web browser. A 404 will be served for any pages or
        resources not in the recorded archive.`

type CommonConfig struct {
	// Info aboth this command.
	cmd cli.Command

	// Flags common to all commands.
	host                                     string
	httpPort, httpsPort, httpSecureProxyPort int
	certFile, keyFile                        string
	injectScripts                            string

	// Computed state.
	root_cert    tls.Certificate
	transformers []webpagereplay.ResponseTransformer
}

type RecordCommand struct {
	common CommonConfig
	cmd    cli.Command
}

type ReplayCommand struct {
	common CommonConfig
	cmd    cli.Command

	// Custom flags for replay.
	rulesFile string
}

func (common *CommonConfig) Flags() []cli.Flag {
	return []cli.Flag{
		cli.StringFlag{
			Name:        "host",
			Value:       "",
			Usage:       "IP address to bind all servers to. Defaults to 127.0.0.1 if not specified.",
			Destination: &common.host,
		},
		cli.IntFlag{
			Name:        "http_port",
			Value:       0,
			Usage:       "Port number to listen on for HTTP requests, or 0 to disable.",
			Destination: &common.httpPort,
		},
		cli.IntFlag{
			Name:        "https_port",
			Value:       0,
			Usage:       "Port number to listen on for HTTPS requests, or 0 to disable.",
			Destination: &common.httpsPort,
		},
		cli.IntFlag{
			Name:        "https_to_http_port",
			Value:       0,
			Usage:       "Port number to listen on for HTTP proxy requests over an HTTPS connection, or 0 to disable.",
			Destination: &common.httpSecureProxyPort,
		},
		cli.StringFlag{
			Name:        "https_cert_file",
			Value:       "wpr_cert.pem",
			Usage:       "File containing a PEM-encoded X509 certificate to use with SSL.",
			Destination: &common.certFile,
		},
		cli.StringFlag{
			Name:        "https_key_file",
			Value:       "wpr_key.pem",
			Usage:       "File containing a PEM-encoded private key to use with SSL.",
			Destination: &common.keyFile,
		},
		cli.StringFlag{
			Name:  "inject_scripts",
			Value: "deterministic.js",
			Usage: "A comma separated list of JavaScript sources to inject in all pages. " +
				"By default a script is injected that eliminates sources of entropy " +
				"such as Date() and Math.random() deterministic. " +
				"CAUTION: Without deterministic.js, many pages will not replay.",
			Destination: &common.injectScripts,
		},
	}
}

func (common *CommonConfig) CheckArgs(c *cli.Context) error {
	if len(c.Args()) > 1 {
		return errors.New("too many args")
	}
	if len(c.Args()) != 1 {
		return errors.New("must specify archive_file")
	}
	if common.httpPort == 0 && common.httpsPort == 0 && common.httpSecureProxyPort == 0 {
		return errors.New("must specify at least one port flag")
	}

	// Load common configs.
	log.Printf("Loading cert from %v\n", common.certFile)
	log.Printf("Loading key from %v\n", common.keyFile)
	var err error
	common.root_cert, err = tls.LoadX509KeyPair(common.certFile, common.keyFile)
	if err != nil {
		return fmt.Errorf("error opening cert or key files: %v", err)
	}
	err = webpagereplay.InstallRoot(common.root_cert.Certificate[0])
	if err != nil {
		return fmt.Errorf("Install root failed: %v", err)
	}
	for _, scriptFile := range strings.Split(common.injectScripts, ",") {
		log.Printf("Loading script from %v\n", scriptFile)
		si, err := webpagereplay.NewScriptInjectorFromFile(scriptFile)
		if err != nil {
			return fmt.Errorf("error opening script %s: %v", scriptFile, err)
		}
		common.transformers = append(common.transformers, si)
	}

	return nil
}

func (r *RecordCommand) Flags() []cli.Flag {
	return r.common.Flags()
}

func (r *ReplayCommand) Flags() []cli.Flag {
	return append(r.common.Flags(),
		cli.StringFlag{
			Name:        "rules_file",
			Value:       "",
			Usage:       "File containing rules to apply to responses during replay",
			Destination: &r.rulesFile,
		})
}

func startServers(tlsconfig *tls.Config, httpHandler, httpsHandler http.Handler, common *CommonConfig) {
	type Server struct {
		Scheme string
		*http.Server
	}

	servers := []*Server{}
	if common.httpPort > 0 {
		servers = append(servers, &Server{
			Scheme: "http",
			Server: &http.Server{
				Addr:    fmt.Sprintf("%v:%v", common.host, common.httpPort),
				Handler: httpHandler,
			},
		})
	}
	if common.httpsPort > 0 {
		servers = append(servers, &Server{
			Scheme: "https",
			Server: &http.Server{
				Addr:      fmt.Sprintf("%v:%v", common.host, common.httpsPort),
				Handler:   httpsHandler,
				TLSConfig: tlsconfig,
			},
		})
	}
	if common.httpSecureProxyPort > 0 {
		servers = append(servers, &Server{
			Scheme: "https",
			Server: &http.Server{
				Addr:      fmt.Sprintf("%v:%v", common.host, common.httpSecureProxyPort),
				Handler:   httpHandler, // this server proxies HTTP requests over an HTTPS connection
				TLSConfig: nil,         // use the default since this is as a proxy, not a MITM server
			},
		})
	}

	for _, s := range servers {
		log.Printf("Starting server on %s://%s", s.Scheme, s.Addr)
		s := s
		go func() {
			var err error
			switch s.Scheme {
			case "http":
				err = s.ListenAndServe()
			case "https":
				err = s.ListenAndServeTLS(common.certFile, common.keyFile)
			default:
				panic(fmt.Sprintf("unknown s.Scheme: %s", s.Scheme))
			}
			if err != nil {
				log.Printf("Failed to start server on %s://%s: %v", s.Scheme, s.Addr, err)
			}
		}()
	}

	log.Printf("Use Ctrl-C to exit.")
	select {}
}

func (r *RecordCommand) Run(c *cli.Context) {
	archiveFileName := c.Args().First()
	archive, err := webpagereplay.OpenWritableArchive(archiveFileName)
	if err != nil {
		cli.ShowSubcommandHelp(c)
		os.Exit(1)
	}
	defer archive.Close()
	log.Printf("Opened archive %s", archiveFileName)

	// Install a SIGINT handler to close the archive before shutting down.
	go func() {
		sigchan := make(chan os.Signal, 1)
		signal.Notify(sigchan, os.Interrupt)
		<-sigchan
		log.Printf("Shutting down")
		log.Printf("Writing archive file to %s", archiveFileName)
		if err := archive.Close(); err != nil {
			log.Printf("Error flushing archive: %v", err)
		}
		webpagereplay.RemoveRoot()
		os.Exit(0)
	}()

	httpHandler := webpagereplay.NewRecordingProxy(archive, "http", r.common.transformers)
	httpsHandler := webpagereplay.NewRecordingProxy(archive, "https", r.common.transformers)
	tlsconfig, err := webpagereplay.RecordTLSConfig(r.common.root_cert, archive)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error creating TLSConfig: %v", err)
		os.Exit(1)
	}
	startServers(tlsconfig, httpHandler, httpsHandler, &r.common)
}

func (r *ReplayCommand) Run(c *cli.Context) {
	archiveFileName := c.Args().First()
	archive, err := webpagereplay.OpenArchive(archiveFileName)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error openining archive file: %v", err)
		os.Exit(1)
	}
	log.Printf("Opened archive %s", archiveFileName)

	if r.rulesFile != "" {
		t, err := webpagereplay.NewRuleBasedTransformer(r.rulesFile)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error opening rules file %s: %v\n", r.rulesFile, err)
			os.Exit(1)
		}
		r.common.transformers = append(r.common.transformers, t)
		log.Printf("Loaded replay rules from %s", r.rulesFile)
	}

	httpHandler := webpagereplay.NewReplayingProxy(archive, "http", r.common.transformers)
	httpsHandler := webpagereplay.NewReplayingProxy(archive, "https", r.common.transformers)
	tlsconfig, err := webpagereplay.ReplayTLSConfig(r.common.root_cert, archive)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error creating TLSConfig: %v", err)
		os.Exit(1)
	}
	startServers(tlsconfig, httpHandler, httpsHandler, &r.common)
}

func main() {
	progName := filepath.Base(os.Args[0])

	var record RecordCommand
	var replay ReplayCommand

	record.cmd = cli.Command{
		Name:   "record",
		Usage:  "Record web pages to an archive",
		Flags:  record.Flags(),
		Before: record.common.CheckArgs,
		Action: record.Run,
	}

	replay.cmd = cli.Command{
		Name:   "replay",
		Usage:  "Replay a previously-recorded web page archive",
		Flags:  replay.Flags(),
		Before: replay.common.CheckArgs,
		Action: replay.Run,
	}

	app := cli.NewApp()
	app.Commands = []cli.Command{record.cmd, replay.cmd}
	app.Usage = "Web Page Replay"
	app.UsageText = fmt.Sprintf(longUsage, progName)
	app.HideVersion = true
	app.Version = ""
	app.Writer = os.Stderr
	app.RunAndExitOnError()
}
