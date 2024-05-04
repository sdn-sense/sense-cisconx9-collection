#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cisconx9 module unit tests."""
__metaclass__ = type

import json

from unittest.mock import *
from ansible_collections.sense.cisconx9.tests.unit.modules.cisconx9_module import TestciscoNX9Module, load_fixture
from ansible_collections.sense.cisconx9.tests.unit.modules.cisconx9_module import set_module_args
from ansible_collections.sense.cisconx9.plugins.modules import cisconx9_facts


class TestciscoNX9Facts(TestciscoNX9Module):
    """Unit tests for cisconx9_facts module."""

    module = cisconx9_facts

    def setUp(self):
        """Setup for each test."""
        super(TestciscoNX9Facts, self).setUp()

        self.mock_run_command = patch(
            'ansible_collections.sense.cisconx9.plugins.modules.cisconx9_facts.run_commands')
        self.run_commands = self.mock_run_command.start()

    def tearDown(self):
        """Cleanup after each test."""
        super(TestciscoNX9Facts, self).tearDown()

        self.mock_run_command.stop()

    def load_fixtures(self, commands=None):
        """Load fixtures from files override."""

        def load_from_file(*args, **kwargs):
            """Load fixture from file."""
            module, commands = args
            output = []

            for item in commands:
                try:
                    obj = json.loads(item)
                    command = obj['command']
                except ValueError:
                    command = item
                if '|' in command:
                    command = str(command).replace('|', '')
                filename = str(command).replace(' ', '_')
                filename = filename.replace('/', '7')
                output.append(load_fixture(filename))
            return output

        self.run_commands.side_effect = load_from_file

    def test_cisconx9_facts_gather_subset_default(self):
        """Test the default gather_subset."""
        set_module_args({})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertEquals('r-sensetb-fcc2-1-new', ansible_facts['ansible_net_hostname'])
        self.assertEquals('cisco Nexus9000C93600CD-GX Chassis', ansible_facts['ansible_net_hwid'])
        self.assertEquals('9.3(10)', ansible_facts['ansible_net_version'])

    def test_cisconx9_facts_gather_subset_config(self):
        """Test the gather_subset=config option."""
        set_module_args({'gather_subset': 'config'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertIn('ansible_net_config', ansible_facts)

    def test_cisconx9_facts_gather_subset_interfaces(self):
        """Test the gather_subset=interfaces option."""
        set_module_args({'gather_subset': 'interfaces'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertIn('ansible_net_interfaces', ansible_facts)
        self.assertIn('Ethernet1/24', ansible_facts['ansible_net_interfaces'])
        self.assertEquals("cmssense4-NVME", ansible_facts['ansible_net_interfaces']['Ethernet1/24']['description'])
        self.assertEquals("up", ansible_facts['ansible_net_interfaces']['Ethernet1/24']['operstatus'])
        self.assertEquals("a4:11:bb:40:c6:b4", ansible_facts['ansible_net_interfaces']['Ethernet1/24']['mac'])
        self.assertEquals("full", ansible_facts['ansible_net_interfaces']['Ethernet1/24']['duplex'])
        self.assertEquals("9216", ansible_facts['ansible_net_interfaces']['Ethernet1/24']['mtu'])
        self.assertIn({'address': '172.24.20.52', 'masklen': '24'}, ansible_facts['ansible_net_interfaces']['mgmt0']['ipv4'])
        self.assertEquals(['Ethernet1/7', 'Ethernet1/21', 'Ethernet1/23', 'Ethernet1/24', 'Ethernet1/25', 'Ethernet1/26', 'Ethernet1/27', 'Ethernet1/1/2', 'Ethernet1/1/4'], ansible_facts['ansible_net_interfaces']['Vlan1323']['tagged'])
        self.assertIn({'address': '2620:6a:0:2841::1', 'masklen': '64'}, ansible_facts['ansible_net_interfaces']['Vlan1312']['ipv6'])
        # Test lldp information
        self.assertIn('Ethernet1/1/3', ansible_facts['ansible_net_lldp'])
        self.assertEquals('00:0e:1e:05:8f:b0', ansible_facts['ansible_net_lldp']['Ethernet1/1/3']['remote_chassis_id'])
        self.assertEquals('r-cms-fcc2-2', ansible_facts['ansible_net_lldp']['Ethernet1/21']['remote_port_id'])
        self.assertEquals('r-sensetb-fcc2-1', ansible_facts['ansible_net_lldp']['Ethernet1/21']['remote_system_name'])

    def test_cisconx9_facts_gather_subset_routing(self):
        """Test the gather_subset=routing option."""
        set_module_args({'gather_subset': 'routing'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertIn("ansible_net_ipv4", ansible_facts)
        self.assertIn({'vrf': 'default', 'to': '0.0.0.0/0', 'from': '231.125.196.129'}, ansible_facts['ansible_net_ipv4'])
        self.assertIn({'vrf': 'default', 'to': '231.125.196.128/27', 'from': '231.125.196.139'}, ansible_facts['ansible_net_ipv4'])
        self.assertIn("ansible_net_ipv6", ansible_facts)
        self.assertIn({'vrf': 'default', 'to': '2b0b:7d:0:2841::1/128', 'from': '2b0b:7d:0:2841::1'}, ansible_facts['ansible_net_ipv6'])
        self.assertIn( {'vrf': 'default', 'to': '2b0b:7d:0:4421::/64', 'from': '2b0b:7d:0:4421:f0:0:196:139'}, ansible_facts['ansible_net_ipv6'])
