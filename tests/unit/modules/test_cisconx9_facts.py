#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__metaclass__ = type

import json

from unittest.mock import *
from ansible_collections.sense.cisconx9.tests.unit.modules.cisconx9_module import TestciscoNX9Module, load_fixture
from ansible_collections.sense.cisconx9.tests.unit.modules.cisconx9_module import set_module_args
from ansible_collections.sense.cisconx9.plugins.modules import cisconx9_facts


class TestciscoNX9Facts(TestciscoNX9Module):

    module = cisconx9_facts

    def setUp(self):
        super(TestciscoNX9Facts, self).setUp()

        self.mock_run_command = patch(
            'ansible_collections.sense.cisconx9.plugins.modules.cisconx9_facts.run_commands')
        self.run_commands = self.mock_run_command.start()

    def tearDown(self):
        super(TestciscoNX9Facts, self).tearDown()

        self.mock_run_command.stop()

    def load_fixtures(self, commands=None):

        def load_from_file(*args, **kwargs):
            module, commands = args
            output = list()

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
        set_module_args(dict())
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertEquals('r-sensetb-fcc2-1', ansible_facts['ansible_net_hostname'])
        self.assertEquals('Nexus9000 C93108TC-EX chassis', ansible_facts['ansible_net_hwid'])
        self.assertEquals('9.3(10)', ansible_facts['ansible_net_version'])

    def test_cisconx9_facts_gather_subset_config(self):
        set_module_args({'gather_subset': 'config'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertIn('ansible_net_config', ansible_facts)

    def test_cisconx9_facts_gather_subset_interfaces(self):
        set_module_args({'gather_subset': 'interfaces'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertIn('ansible_net_interfaces', ansible_facts)
        self.assertIn('Ethernet1/53', ansible_facts['ansible_net_interfaces'])
        self.assertEquals("SENSE-TB", ansible_facts['ansible_net_interfaces']['Ethernet1/53']['description'])
        self.assertEquals("up", ansible_facts['ansible_net_interfaces']['Ethernet1/53']['operstatus'])
        self.assertEquals("d4:78:9b:19:d1:60", ansible_facts['ansible_net_interfaces']['Ethernet1/53']['mac'])
        self.assertEquals("full", ansible_facts['ansible_net_interfaces']['Ethernet1/53']['duplex'])
        self.assertEquals("9216", ansible_facts['ansible_net_interfaces']['Ethernet1/53']['mtu'])
        self.assertIn({'address': '172.24.20.216', 'masklen': '24'}, ansible_facts['ansible_net_interfaces']['mgmt0']['ipv4'])
        self.assertEquals(['Ethernet1/2', 'Ethernet1/49', 'Ethernet1/51', 'Ethernet1/52'], ansible_facts['ansible_net_interfaces']['Vlan1323']['tagged'])

        self.assertIn({'address': '2a0b:7d:0:4840::1', 'masklen': '64'}, ansible_facts['ansible_net_interfaces']['Vlan1323']['ipv6'])

        # Test lldp information
        self.assertIn('Ethernet1/53', ansible_facts['ansible_net_lldp'])
        self.assertEquals('e8:eb:d3:cc:e1:2c', ansible_facts['ansible_net_lldp']['Ethernet1/53']['remote_chassis_id'])
        self.assertEquals('enp129s0f0', ansible_facts['ansible_net_lldp']['Ethernet1/53']['remote_port_id'])
        self.assertEquals('cmssense2.fnal.gov', ansible_facts['ansible_net_lldp']['Ethernet1/53']['remote_system_name'])

    def test_cisconx9_facts_gather_subset_routing(self):
        set_module_args({'gather_subset': 'routing'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertIn("ansible_net_ipv4", ansible_facts)
        self.assertIn({'vrf': 'CMSTB', 'to': '0.0.0.0/0', 'from': '231.125.196.129'}, ansible_facts['ansible_net_ipv4'])
        self.assertIn({'vrf': 'CMSTB', 'to': '231.125.196.128/27', 'from': '231.125.196.139'}, ansible_facts['ansible_net_ipv4'])
        self.assertIn("ansible_net_ipv6", ansible_facts)
        self.assertIn({'vrf': 'default', 'to': '2a0b:7d:0:2841::1/128', 'from': '2a0b:7d:0:2841::1'}, ansible_facts['ansible_net_ipv6'])
        self.assertIn( {'vrf': 'CMSTB', 'to': '2a0b:7d:0:4421::/64', 'from': '2a0b:7d:0:4421:f0:0:196:139'}, ansible_facts['ansible_net_ipv6'])