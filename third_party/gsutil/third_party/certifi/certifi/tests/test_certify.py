# -*- coding: utf-8 -*-

import os
import unittest

import certifi


class TestCertifi(unittest.TestCase):
    def test_cabundle_exists(self):
        assert os.path.exists(certifi.where())

    def test_read_contents(self):
        content = certifi.contents()
        assert "-----BEGIN CERTIFICATE-----" in content
