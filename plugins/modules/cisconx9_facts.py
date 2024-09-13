#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
import traceback

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import iteritems
from ansible.utils.display import Display
from ansible_collections.sense.cisconx9.plugins.module_utils.network.cisconx9 import (
    check_args, cisconx9_argument_spec, run_commands)
from ansible_collections.sense.cisconx9.plugins.module_utils.runwrapper import classwrapper, functionwrapper

display = Display()


@classwrapper
class FactsBase:
    """Base class for Facts"""

    COMMANDS = []

    def __init__(self, module):
        self.module = module
        self.facts = {}
        self.responses = None

    def populate(self):
        """Populate responses"""
        self.responses = run_commands(self.module, self.COMMANDS, check_rc=False)

    def run(self, cmd):
        """Run commands"""
        return run_commands(self.module, cmd, check_rc=False)

@classwrapper
class Default(FactsBase):
    """Default Class to get basic info"""

    COMMANDS = [
        "show version | json",
    ]

    def populate(self):
        super(Default, self).populate()
        data = self.responses[0]
        for key, outkey in {
            "chassis_id": "hwid",
            "host_name": "hostname",
            "rr_sys_ver": "version",
        }.items():
            if key in data and data[key]:
                self.facts[outkey] = data[key]


@classwrapper
class Config(FactsBase):
    """Default Class to get basic info"""

    COMMANDS = [
        "show running-config | json",
    ]

    def populate(self):
        super(Config, self).populate()
        self.facts["config"] = self.responses[0]


@classwrapper
class Interfaces(FactsBase):
    """All Interfaces Class"""

    COMMANDS = [
        "show interface | json",
        "show vlan | json",
        "show ipv6 interface vrf all | json",
        "show lldp neighbors detail | json",
    ]

    @staticmethod
    def macSplitter(inputmac):
        """Split mac address (by .) into separated format and rejoin to :."""
        macaddr = inputmac.strip().replace(".", "")
        split_mac = [macaddr[index : index + 2] for index in range(0, len(macaddr), 2)]
        return ":".join(split_mac)


    @staticmethod
    def _validate(indata, keys):
        """Validate response and preset default values"""
        if isinstance(indata, dict):
            display.vvv(f"Data is not a dictionary: {indata}. Rewrite as dict")
            indata = {}
        tmpval = indata
        for key, keytype, default in keys:
            if key not in tmpval:
                display.vvv(f"Key not found: {key} in {indata}")
                tmpval[key] = default
            if not isinstance(tmpval[key], keytype):
                display.vvv(f"Key {key} is not of type {keytype} in {indata}")
                tmpval[key] = default
            tmpval = tmpval[key]
        return indata



    def populate_vlan(self, intdict, intout):
        """Populate vlan output information"""
        if "svi_line_proto" in intdict:
            intout["operstatus"] = intdict["svi_line_proto"]
        if "svi_bw" in intdict:
            intout["bandwidth"] = int(int(intdict["svi_bw"]) / 1000)
        if "svi_ip_addr" in intdict and "svi_ip_mask" in intdict:
            intout.setdefault("ipv4", [])
            intout["ipv4"].append(
                {"address": intdict["svi_ip_addr"], "masklen": intdict["svi_ip_mask"]}
            )
        if "svi_mac" in intdict:
            newmac = self.macSplitter(intdict["svi_mac"])
            intout["mac"] = newmac
            if newmac not in self.facts["info"]["macs"]:
                self.facts["info"]["macs"].append(newmac)
        if "svi_mtu" in intdict:
            intout["mtu"] = intdict["svi_mtu"]

    def populate_eth(self, intdict, intout):
        """Populate eth output information"""
        if "state" in intdict:
            intout["operstatus"] = intdict["state"]
        if "eth_hw_addr" in intdict:
            newmac = self.macSplitter(intdict["eth_hw_addr"])
            intout["mac"] = newmac
            if newmac not in self.facts["info"]["macs"]:
                self.facts["info"]["macs"].append(newmac)
        if "eth_duplex" in intdict:
            intout["duplex"] = intdict["eth_duplex"]
        if "desc" in intdict:
            intout["description"] = intdict["desc"]
        if "eth_ip_addr" in intdict and "eth_ip_mask" in intdict:
            intout.setdefault("ipv4", [])
            intout["ipv4"].append(
                {"address": intdict["eth_ip_addr"], "masklen": intdict["eth_ip_mask"]}
            )
        if "eth_bw" in intdict:
            intout["bandwidth"] = int(int(intdict["eth_bw"]) / 1000)
        if "eth_mtu" in intdict:
            intout["mtu"] = intdict["eth_mtu"]
        if "eth_mode" in intdict and intdict["eth_mode"] == "trunk":
            intout["switchport"] = "yes"
        else:
            intout["switchport"] = "no"

    def populate_lldp(self):
        """Populate lldp information"""
        lldpdict = self.facts.setdefault("lldp", {})
        self.responses[3] = self._validate(self.responses[3], [["TABLE_nbor_detail", dict, {}], ["ROW_nbor_detail", list, []]])
        for intdict in (
            self.responses[3].get("TABLE_nbor_detail", {}).get("ROW_nbor_detail", [])
        ):
            tmpdict = {}
            if "l_port_id" in intdict:
                tmpdict["local_port_id"] = intdict["l_port_id"].replace(
                    "Eth", "Ethernet"
                )
            if "port_id" in intdict:
                newmac = self.macSplitter(intdict["port_id"])
                tmpdict["remote_chassis_id"] = newmac
            if "port_desc" in intdict and intdict["port_desc"] != "null":
                tmpdict["remote_port_id"] = intdict["port_desc"]
            if "sys_name" in intdict and intdict["sys_name"] != "null":
                tmpdict["remote_system_name"] = intdict["sys_name"]
            if tmpdict["local_port_id"]:
                lldpdict[tmpdict["local_port_id"]] = tmpdict

    def populate(self):
        super(Interfaces, self).populate()

        self.facts.setdefault("interfaces", {})
        self.facts.setdefault("info", {"macs": []})
        self.responses[0] =self._validate(self.responses[0], [["TABLE_interface", dict, {}], ["ROW_interface", list, []]])
        for intdict in (
            self.responses[0].get("TABLE_interface", {}).get("ROW_interface", [])
        ):
            # interface name
            if "interface" not in intdict:
                continue
            intout = self.facts["interfaces"].setdefault(intdict["interface"], {})
            if intdict["interface"].startswith("Vlan"):
                self.populate_vlan(intdict, intout)
            else:
                self.populate_eth(intdict, intout)

        self.responses[1] = self._validate(self.responses[1], [["TABLE_vlanbrief", dict, {}], ["ROW_vlanbrief", list, []]])
        for intdict in (
            self.responses[1].get("TABLE_vlanbrief", {}).get("ROW_vlanbrief", [])
        ):
            intf = f"Vlan{intdict['vlanshowbr-vlanid']}"
            vlanout = self.facts["interfaces"].setdefault(intf, {})
            vlanout["description"] = intdict["vlanshowbr-vlanname"]
            if "vlanshowbr-vlanname" in intdict:
                vlanout["description"] = intdict["vlanshowbr-vlanname"]
            if "vlanshowbr-vlanstate" in intdict:
                vlanout["operstatus"] = intdict["vlanshowbr-vlanstate"]
            if "vlanshowplist-ifidx" in intdict:
                vlanout.setdefault("tagged", intdict["vlanshowplist-ifidx"].split(","))
        # IPv6s (for IPv4 it is available from interfaces output)
        # show ipv6 interface vrf all | json,
        self.responses[2] = self._validate(self.responses[2], [["TABLE_intf", dict, {}], ["ROW_intf", list, []]])
        for intdict in self.responses[2].get("TABLE_intf", {}).get("ROW_intf", []):
            intout = self.facts["interfaces"].setdefault(intdict["intf-name"], {})
            tmpips = intdict.get("TABLE_addr", {}).get("ROW_addr", [])
            if isinstance(tmpips, list):
                for addr in intdict.get("TABLE_addr", {}).get("ROW_addr", []):
                    ipv6spl = addr["addr"].split("/")
                    intout.setdefault("ipv6", [])
                    intout["ipv6"].append(
                        {"address": ipv6spl[0], "masklen": ipv6spl[1]}
                    )
            else:
                tmpipv6 = (
                    intdict.get("TABLE_addr", {}).get("ROW_addr", []).get("addr", None)
                )
                if tmpipv6:
                    ipv6spl = tmpipv6.split("/")
                    intout.setdefault("ipv6", [])
                    intout["ipv6"].append(
                        {"address": ipv6spl[0], "masklen": ipv6spl[1]}
                    )
        # Populate lldp information
        self.populate_lldp()


@classwrapper
class Routing(FactsBase):
    """Routing Information Class"""

    COMMANDS = ["show ip route vrf all | json", "show ipv6 route vrf all | json"]

    def populate_ip46(self, respid, resptype):
        """Populate IP routing information"""
        self.facts.setdefault(resptype, [])
        for intdict in self.responses[respid].get("TABLE_vrf", {}).get("ROW_vrf", []):
            for routeEntry in (
                intdict.get("TABLE_addrf", {})
                .get("ROW_addrf")
                .get("TABLE_prefix", {})
                .get("ROW_prefix", [])
            ):
                if not isinstance(routeEntry, dict):
                    continue
                tmpdict = {"vrf": intdict["vrf-name-out"]}
                if "ipprefix" in routeEntry:
                    tmpdict["to"] = routeEntry["ipprefix"]
                rfrom = (
                    routeEntry.get("TABLE_path", {})
                    .get("ROW_path", {}))
                if isinstance(rfrom, list):
                    for entry in rfrom:
                        if entry.get("ipnexthop", None):
                            tmpdict["from"] = entry.get("ipnexthop")
                        self.facts[resptype].append(tmpdict)
                elif rfrom.get("ipnexthop", None):
                    tmpdict["from"] = rfrom.get("ipnexthop")
                    self.facts[resptype].append(tmpdict)

    def populate(self):
        super(Routing, self).populate()
        try:
            self.populate_ip46(0, "ipv4")
        except Exception:
            pass
        try:
            self.populate_ip46(1, "ipv6")
        except Exception:
            pass


FACT_SUBSETS = {
    "default": Default,
    "interfaces": Interfaces,
    "routing": Routing,
    "config": Config,
}

VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())

@functionwrapper
def main():
    """main entry point for module execution"""
    argument_spec = {"gather_subset": {"default": ["!config"], "type": "list"}}
    argument_spec.update(cisconx9_argument_spec)
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    gather_subset = module.params["gather_subset"]
    runable_subsets = set()
    exclude_subsets = set()

    for subset in gather_subset:
        if subset == "all":
            runable_subsets.update(VALID_SUBSETS)
            continue
        if subset.startswith("!"):
            subset = subset[1:]
            if subset == "all":
                exclude_subsets.update(VALID_SUBSETS)
                continue
            exclude = True
        else:
            exclude = False
        if subset not in VALID_SUBSETS:
            module.fail_json(msg="Bad subset")
        if exclude:
            exclude_subsets.add(subset)
        else:
            runable_subsets.add(subset)
    if not runable_subsets:
        runable_subsets.update(VALID_SUBSETS)

    runable_subsets.difference_update(exclude_subsets)
    runable_subsets.add("default")

    facts = {"gather_subset": [runable_subsets]}

    instances = []
    for key in runable_subsets:
        instances.append(FACT_SUBSETS[key](module))

    for inst in instances:
        if inst:
            try:
                inst.populate()
                facts.update(inst.facts)
            except Exception as ex:
                display.vvv(traceback.format_exc())
                raise Exception(traceback.format_exc()) from ex

    ansible_facts = {}
    for key, value in iteritems(facts):
        key = f"ansible_net_{key}"
        ansible_facts[key] = value

    warnings = []
    check_args(module, warnings)
    module.exit_json(ansible_facts=ansible_facts, warnings=warnings)


if __name__ == "__main__":
    main()
