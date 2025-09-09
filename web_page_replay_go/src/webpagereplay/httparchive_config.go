// Copyright 2025 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package webpagereplay

import (
	"github.com/urfave/cli/v2"
)


type HttpArchiveConfig struct {
	method, host, fullPath                                           string
	statusCode                                                       int
	decodeResponseBody, skipExisting, overwriteExisting, invertMatch bool
}

func (cfg *HttpArchiveConfig) RequestFilterFlags() []cli.Flag {
	return []cli.Flag{
		&cli.StringFlag{
			Name:        "command",
			Value:       "",
			Usage:       "Only include URLs matching this HTTP method.",
			Destination: &cfg.method,
		},
		&cli.StringFlag{
			Name:        "host",
			Value:       "",
			Usage:       "Only include URLs matching this host.",
			Destination: &cfg.host,
		},
		&cli.StringFlag{
			Name:        "full_path",
			Value:       "",
			Usage:       "Only include URLs matching this full path.",
			Destination: &cfg.fullPath,
		},
		&cli.IntFlag{
			Name:        "status_code",
			Value:       0,
			Usage:       "Only include URLs matching this response status code.",
			Destination: &cfg.statusCode,
		},
	}
}

func (cfg *HttpArchiveConfig) DefaultFlags() []cli.Flag {
	return append([]cli.Flag{
		&cli.BoolFlag{
			Name:        "decode_response_body",
			Usage:       "Decode/encode response body according to Content-Encoding header.",
			Destination: &cfg.decodeResponseBody,
		},
	}, cfg.RequestFilterFlags()...)
}

func (cfg *HttpArchiveConfig) AddFlags() []cli.Flag {
	return []cli.Flag{
		&cli.BoolFlag{
			Name:        "skip-existing",
			Usage:       "Skip over existing urls in the archive",
			Destination: &cfg.skipExisting,
		},
		&cli.BoolFlag{
			Name:        "overwrite-existing",
			Usage:       "Overwrite existing urls in the archive",
			Destination: &cfg.overwriteExisting,
		},
	}
}

func (cfg *HttpArchiveConfig) TrimFlags() []cli.Flag {
	return append([]cli.Flag{
		&cli.BoolFlag{
			Name:        "invert-match",
			Usage:       "Trim away any urls that DON'T match in the archive",
			Destination: &cfg.invertMatch,
		},
	}, cfg.DefaultFlags()...)
}
