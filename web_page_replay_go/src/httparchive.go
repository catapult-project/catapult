// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Program httparchive prints information about archives saved by record.
package main

import (
	"bufio"
	"bytes"
	"crypto"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"./webpagereplay"
	"github.com/urfave/cli"
)

const usage = "%s [ls|cat|edit|merge|add|addAll] [options] archive_file [output_file] [url]"

type CertConfig struct {
	// Flags common to all commands.
	certFile, keyFile string
}

func (certCfg *CertConfig) Flags() []cli.Flag {
	return []cli.Flag{
		cli.StringFlag{
			Name:        "https_cert_file",
			Value:       "wpr_cert.pem",
			Usage:       "File containing a PEM-encoded X509 certificate to use with SSL.",
			Destination: &certCfg.certFile,
		},
		cli.StringFlag{
			Name:        "https_key_file",
			Value:       "wpr_key.pem",
			Usage:       "File containing a PEM-encoded private key to use with SSL.",
			Destination: &certCfg.keyFile,
		},
	}
}

type Config struct {
	method, host, fullPath                              string
	decodeResponseBody, skipExisting, overwriteExisting bool
	certConfig                                          CertConfig
	root_cert                                           tls.Certificate
}

func (cfg *Config) DefaultFlags() []cli.Flag {
	return append(cfg.certConfig.Flags(),

		cli.StringFlag{
			Name:        "command",
			Value:       "",
			Usage:       "Only show URLs matching this HTTP method.",
			Destination: &cfg.method,
		},
		cli.StringFlag{
			Name:        "host",
			Value:       "",
			Usage:       "Only show URLs matching this host.",
			Destination: &cfg.host,
		},
		cli.StringFlag{
			Name:        "full_path",
			Value:       "",
			Usage:       "Only show URLs matching this full path.",
			Destination: &cfg.fullPath,
		},
		cli.BoolFlag{
			Name:        "decode_response_body",
			Usage:       "Decode/encode response body according to Content-Encoding header.",
			Destination: &cfg.decodeResponseBody,
		},
	)

}

func (cfg *Config) AddFlags() []cli.Flag {
	return []cli.Flag{
		cli.BoolFlag{
			Name:        "skip-existing",
			Usage:       "Skip over existing urls in the archive",
			Destination: &cfg.skipExisting,
		},
		cli.BoolFlag{
			Name:        "overwrite-existing",
			Usage:       "Overwrite existing urls in the archive",
			Destination: &cfg.overwriteExisting,
		},
	}
}

func (cfg *Config) requestEnabled(req *http.Request) bool {
	if cfg.method != "" && strings.ToUpper(cfg.method) != req.Method {
		return false
	}
	if cfg.host != "" && cfg.host != req.Host {
		return false
	}
	if cfg.fullPath != "" && cfg.fullPath != req.URL.Path {
		return false
	}
	return true
}

func list(cfg *Config, a *webpagereplay.Archive, printFull bool) error {
	return a.ForEach(func(req *http.Request, resp *http.Response) error {
		if !cfg.requestEnabled(req) {
			return nil
		}
		if printFull {
			fmt.Fprint(os.Stdout, "----------------------------------------\n")
			req.Write(os.Stdout)
			fmt.Fprint(os.Stdout, "\n")
			err := webpagereplay.DecompressResponse(resp)
			if err != nil {
				return fmt.Errorf("Unable to decompress body:\n%v", err)
			}
			resp.Write(os.Stdout)
			fmt.Fprint(os.Stdout, "\n")
		} else {
			fmt.Fprintf(os.Stdout, "%s %s %s\n", req.Method, req.Host, req.URL)
		}
		return nil
	})
}

func edit(cfg *Config, a *webpagereplay.Archive, outfile string) error {
	editor := os.Getenv("EDITOR")
	if editor == "" {
		fmt.Printf("Warning: EDITOR not specified, using default.\n")
		editor = "vi"
	}

	marshalForEdit := func(w io.Writer, req *http.Request, resp *http.Response) error {
		if err := req.Write(w); err != nil {
			return err
		}
		if cfg.decodeResponseBody {
			if err := webpagereplay.DecompressResponse(resp); err != nil {
				return fmt.Errorf("couldn't decompress body: %v", err)
			}
		}
		return resp.Write(w)
	}

	unmarshalAfterEdit := func(r io.Reader) (*http.Request, *http.Response, error) {
		br := bufio.NewReader(r)
		req, err := http.ReadRequest(br)
		if err != nil {
			return nil, nil, fmt.Errorf("couldn't unmarshal request: %v", err)
		}
		resp, err := http.ReadResponse(br, req)
		if err != nil {
			if req.Body != nil {
				req.Body.Close()
			}
			return nil, nil, fmt.Errorf("couldn't unmarshal response: %v", err)
		}
		if cfg.decodeResponseBody {
			// Compress body back according to Content-Encoding
			if err := compressResponse(resp); err != nil {
				return nil, nil, fmt.Errorf("couldn't compress response: %v", err)
			}
		}
		// Read resp.Body into a buffer since the tmpfile is about to be deleted.
		body, err := ioutil.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			return nil, nil, fmt.Errorf("couldn't unmarshal response body: %v", err)
		}
		resp.Body = ioutil.NopCloser(bytes.NewReader(body))
		return req, resp, nil
	}

	newA, err := a.Edit(func(req *http.Request, resp *http.Response) (*http.Request, *http.Response, error) {
		if !cfg.requestEnabled(req) {
			return req, resp, nil
		}
		fmt.Printf("Editing request: host=%s uri=%s\n", req.Host, req.URL.String())
		// Serialize the req/resp to a temporary file, let the user edit that file, then
		// de-serialize and return the result. Repeat until de-serialization succeeds.
		for {
			tmpf, err := ioutil.TempFile("", "httparchive_edit_request")
			if err != nil {
				return nil, nil, err
			}
			tmpname := tmpf.Name()
			defer os.Remove(tmpname)
			if err := marshalForEdit(tmpf, req, resp); err != nil {
				tmpf.Close()
				return nil, nil, err
			}
			if err := tmpf.Close(); err != nil {
				return nil, nil, err
			}
			// Edit this file.
			cmd := exec.Command(editor, tmpname)
			cmd.Stdin = os.Stdin
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
			if err := cmd.Run(); err != nil {
				return nil, nil, fmt.Errorf("Error running %s %s: %v", editor, tmpname, err)
			}
			// Reload.
			tmpf, err = os.Open(tmpname)
			if err != nil {
				return nil, nil, err
			}
			defer tmpf.Close()
			newReq, newResp, err := unmarshalAfterEdit(tmpf)
			if err != nil {
				fmt.Printf("Error in editing request. Try again: %v\n", err)
				continue
			}
			return newReq, newResp, nil
		}
	})
	if err != nil {
		return fmt.Errorf("error editing archive:\n%v", err)
	}

	return writeArchive(newA, outfile)
}

func writeArchive(archive *webpagereplay.Archive, outfile string) error {
	outf, err := os.OpenFile(outfile, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, os.FileMode(0660))
	if err != nil {
		return fmt.Errorf("error opening output file %s:\n%v", outfile, err)
	}
	err0 := archive.Serialize(outf)
	err1 := outf.Close()
	if err0 != nil || err1 != nil {
		if err0 == nil {
			err0 = err1
		}
		return fmt.Errorf("error writing edited archive to %s:\n%v", outfile, err0)
	}
	fmt.Printf("Wrote edited archive to %s\n", outfile)
	return nil
}

func merge(cfg *Config, archive *webpagereplay.Archive, input *webpagereplay.Archive, outfile string) error {
	if err := archive.Merge(input); err != nil {
		return fmt.Errorf("Merge archives failed: %v", err)
	}

	return writeArchive(archive, outfile)
}

func addUrl(cfg *Config, archive *webpagereplay.Archive, urlString string) error {
	addMode := webpagereplay.AddModeAppend
	if cfg.skipExisting {
		addMode = webpagereplay.AddModeSkipExisting
	} else if cfg.overwriteExisting {
		addMode = webpagereplay.AddModeOverwriteExisting
	}
	if err := archive.Add("GET", urlString, addMode); err != nil {
		return fmt.Errorf("Error adding request: %v", err)
	}
	return nil
}

func add(cfg *Config, archive *webpagereplay.Archive, outfile string, urls []string) error {
	for _, urlString := range urls {
		if err := addUrl(cfg, archive, urlString); err != nil {
			return err
		}
	}
	return writeArchive(archive, outfile)
}

func addAll(cfg *Config, archive *webpagereplay.Archive, outfile string, inputFilePath string) error {
	f, err := os.OpenFile(inputFilePath, os.O_RDONLY, os.ModePerm)
	if err != nil {
		return fmt.Errorf("open file error: %v", err)
	}
	defer f.Close()

	sc := bufio.NewScanner(f)
	for sc.Scan() {
		urlString := sc.Text() // GET the line string
		if err := addUrl(cfg, archive, urlString); err != nil {
			return err
		}
	}
	if err := sc.Err(); err != nil {
		return fmt.Errorf("scan file error: %v", err)
	}

	return writeArchive(archive, outfile)
}

func restrictSSLCertSANs(cfg *Config, archive *webpagereplay.Archive, outfile string) error {

	var ipMap = make(map[string][]string)

	//Find hosts present in the requests collection & assigns certificates and host ips for these
	requestHostsDict := make(map[string]string)
	for requestHost := range archive.Requests {
		if _, ok := requestHostsDict[requestHost]; !ok {
			requestHostsDict[requestHost] = requestHost
		}
	}
	for k := range requestHostsDict {
		dialer := &net.Dialer{
			Timeout:   30 * time.Second,
			KeepAlive: 30 * time.Second,
			DualStack: true,
		}
		conn, err := tls.DialWithDialer(dialer, "tcp", fmt.Sprintf("%s:443", requestHostsDict[k]), &tls.Config{
			NextProtos: []string{"h2", "http/1.1"},
		})
		if err == nil {
			_, ok := archive.RemoteAddresses[requestHostsDict[k]]
			if !ok {
				fakecert, err := x509.ParseCertificate(cfg.root_cert.Certificate[0])
				if err == nil {
					currCert, er := CreateDomainRestrictedCert([]string{requestHostsDict[k]}, conn.ConnectionState().PeerCertificates[0], fakecert, cfg.root_cert.PrivateKey)
					if er == nil {
						if archive.RemoteAddresses == nil {
							archive.RemoteAddresses = make(map[string]string)
						}
						archive.RemoteAddresses[requestHostsDict[k]] = conn.RemoteAddr().String()

						if _, ok := archive.NegotiatedProtocol[requestHostsDict[k]]; !ok {
							archive.NegotiatedProtocol[requestHostsDict[k]] = conn.ConnectionState().NegotiatedProtocol
						}
						if _, ok := archive.Certs[requestHostsDict[k]]; !ok {
							archive.Certs[requestHostsDict[k]] = currCert
						}
					}
				}
			}
		}
	}

	for host, ip := range archive.RemoteAddresses {
		if h, ok := ipMap[ip]; ok {
			h = append(h, host)
			ipMap[ip] = h
		} else {
			ipMap[ip] = []string{host}
		}
	}

	for ip := range ipMap {
		for i := range ipMap[ip] {
			currentSANList := []string{ipMap[ip][i]}
			currentCert, err := x509.ParseCertificate(archive.Certs[ipMap[ip][i]])
			//derBytes, negotiatedProtocol, ip, err := archive.FindHostTLSConfig(i)
			if err != nil {
				return err
			}
			for j := range ipMap[ip] {
				if j != i {
					certValidationErr := currentCert.VerifyHostname(ipMap[ip][j])
					if certValidationErr == nil {
						currentSANList = append(currentSANList, ipMap[ip][j])
					}
				}
			}

			fakecert, e := x509.ParseCertificate(cfg.root_cert.Certificate[0])

			if e != nil {
				println(fmt.Sprintf("New Cert DNS : %v", e))
			}

			newCert, err := CreateDomainRestrictedCert(currentSANList, currentCert, fakecert, cfg.root_cert.PrivateKey)
			newCertParsed, er := x509.ParseCertificate(newCert)
			if er == nil {
				println(fmt.Sprintf("New Cert CN: %s", newCertParsed.Subject.CommonName))
				println(fmt.Sprintf("Old Cert CN: %s", currentCert.Subject.CommonName))

				for str := range newCertParsed.DNSNames {
					println(fmt.Sprintf("IP: %s New Cert DNS : %s", ip, newCertParsed.DNSNames[str]))
				}
				for str := range currentCert.DNSNames {
					println(fmt.Sprintf("IP: %s Old Cert DNS : %s", ip, currentCert.DNSNames[str]))
				}
			}

			archive.Certs[ipMap[ip][i]] = newCert

		}
	}

	return writeArchive(archive, outfile)
}

//Mints a restricted certificate that is only valid for the SANs in the certificateSAN parameter
func CreateDomainRestrictedCert(certificateSANs []string, rootCert *x509.Certificate, fakecert *x509.Certificate, rootKey crypto.PrivateKey) ([]byte, error) {
	template := x509.Certificate{

		SerialNumber: rootCert.SerialNumber,

		Subject: pkix.Name{

			CommonName: certificateSANs[0],
		},

		Issuer: fakecert.Subject,

		NotBefore: time.Now(),

		NotAfter: time.Now().Add(time.Hour * 24 * 180),

		KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature | x509.KeyUsageCRLSign,

		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth, x509.ExtKeyUsageServerAuth},

		BasicConstraintsValid: true,

		IsCA: true,

		AuthorityKeyId: rootCert.AuthorityKeyId,

		CRLDistributionPoints: rootCert.CRLDistributionPoints,

		IssuingCertificateURL: rootCert.IssuingCertificateURL,

		DNSNames: certificateSANs,

		PublicKey: rootCert.PublicKey,
	}

	derBytes, err := x509.CreateCertificate(rand.Reader, &template, fakecert, fakecert.PublicKey, rootKey)

	return derBytes, err

}

// compressResponse compresses resp.Body in place according to resp's Content-Encoding header.
func compressResponse(resp *http.Response) error {
	ce := strings.ToLower(resp.Header.Get("Content-Encoding"))
	if ce == "" {
		return nil
	}
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	resp.Body.Close()

	body, newCE, err := webpagereplay.CompressBody(ce, body)
	if err != nil {
		return err
	}
	if ce != newCE {
		return fmt.Errorf("can't compress body to '%s' recieved Content-Encoding: '%s'", ce, newCE)
	}
	resp.Body = ioutil.NopCloser(bytes.NewReader(body))
	return nil
}

func main() {
	progName := filepath.Base(os.Args[0])
	cfg := &Config{}

	fail := func(c *cli.Context, err error) {
		fmt.Fprintf(os.Stderr, "Error:\n%v.\n\n", err)
		cli.ShowSubcommandHelp(c)
		os.Exit(1)
	}

	checkArgs := func(cmdName string, wantArgs int) func(*cli.Context) error {
		return func(c *cli.Context) error {
			if len(c.Args()) != wantArgs {
				return fmt.Errorf("Expected %d arguments but got %d", wantArgs, len(c.Args()))
			}
			cfg.certConfig.certFile = "wpr_cert.pem"
			cfg.certConfig.keyFile = "wpr_key.pem"
			log.Printf("Loading cert from %v\n", cfg.certConfig.certFile)
			log.Printf("Loading key from %v\n", cfg.certConfig.keyFile)
			var err error
			cfg.root_cert, err = tls.LoadX509KeyPair(cfg.certConfig.certFile, cfg.certConfig.keyFile)
			if err != nil {
				return fmt.Errorf("error opening cert or key files: %v", err)
			}
			return nil
		}
	}
	loadArchiveOrDie := func(c *cli.Context, arg int) *webpagereplay.Archive {
		archive, err := webpagereplay.OpenArchive(c.Args().Get(arg))
		if err != nil {
			fail(c, err)
		}
		return archive
	}

	app := cli.NewApp()
	app.Commands = []cli.Command{
		cli.Command{
			Name:      "ls",
			Usage:     "List the requests in an archive",
			ArgsUsage: "archive",
			Flags:     cfg.DefaultFlags(),
			Before:    checkArgs("ls", 1),
			Action:    func(c *cli.Context) error {
				return list(cfg, loadArchiveOrDie(c, 0), false)
			},
		},
		cli.Command{
			Name:      "cat",
			Usage:     "Dump the requests/responses in an archive",
			ArgsUsage: "archive",
			Flags:     cfg.DefaultFlags(),
			Before:    checkArgs("cat", 1),
			Action:    func(c *cli.Context) error {
				return list(cfg, loadArchiveOrDie(c, 0), true)
			},
		},
		cli.Command{
			Name:      "edit",
			Usage:     "Edit the requests/responses in an archive",
			ArgsUsage: "input_archive output_archive",
			Flags:     cfg.DefaultFlags(),
			Before:    checkArgs("edit", 2),
			Action:    func(c *cli.Context) error {
				return edit(cfg, loadArchiveOrDie(c, 0), c.Args().Get(1))
			},
		},
		cli.Command{
			Name:      "merge",
			Usage:     "Merge the requests/responses of two archives",
			ArgsUsage: "base_archive input_archive output_archive",
			Before:    checkArgs("merge", 3),
			Action:    func(c *cli.Context) error {
				return merge(cfg, loadArchiveOrDie(c, 0), loadArchiveOrDie(c, 1), c.Args().Get(2))
			},
		},
		cli.Command{
			Name:      "add",
			Usage:     "Add a simple GET request from the network to the archive",
			ArgsUsage: "input_archive output_archive [urls...]",
			Flags:     cfg.AddFlags(),
			Before:    func(c *cli.Context) error {
				if len(c.Args()) < 3 {
					return fmt.Errorf("Expected at least 3 arguments but got %d", len(c.Args()))
				}
				return nil
			},
			Action:    func(c *cli.Context) error {
				return add(cfg, loadArchiveOrDie(c, 0), c.Args().Get(1), c.Args()[2:])
			},
		},
		cli.Command{
			Name:      "addAll",
			Usage:     "Add a simple GET request from the network to the archive",
			ArgsUsage: "input_archive output_archive urls_file",
			Flags:     cfg.AddFlags(),
			Before:    checkArgs("add", 3),
			Action:    func(c *cli.Context) error {
				return addAll(cfg, loadArchiveOrDie(c, 0), c.Args().Get(1), c.Args().Get(2))
			},
		},
		cli.Command{
			Name:      "restrictSSLCertSANs",
			Usage:     "Transforms the certificates in the archives to only those SANs that were served from the IP address",
			ArgsUsage: "input_archive output_archive urls_file",
			Flags:     cfg.AddFlags(),
			Before:    checkArgs("restrictSSLCertSANs", 2),
			Action: func(c *cli.Context) error {
				return restrictSSLCertSANs(cfg, loadArchiveOrDie(c, 0), c.Args().Get(1))
			},
		},
	}
	app.Usage = "HTTP Archive Utils"
	app.UsageText = fmt.Sprintf(usage, progName)
	app.HideVersion = true
	app.Version = ""
	app.Writer = os.Stderr
	err := app.Run(os.Args)
	if err != nil {
		fmt.Printf("%v\n", err)
		os.Exit(1)
	}
}
