#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cisco NX9 BGP Summary
Copyright: Contributors to the SENSE Project
GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

Runs 'show bgp [vrf <vrf>] <afi> unicast summary | json' and normalizes the
result into the shared SiteRM BGP schema:
{"vrf": ..., "afi_checked": [...], "peers": [...]}

NX-OS's JSON output has no advertised/sent-prefix counter in the summary
view at all, so when 'detail' is requested (default True), one extra
plain-text call per established peer -- 'show ip[v6] bgp neighbors
<peer-ip>' -- fills in prefixes_advertised via a flat regex (no JSON
nesting needed for that part).

Parser gotcha: NX-OS collapses a TABLE_x/ROW_x block with exactly one
entry into a bare dict instead of a list of one dict (confirmed live).
asList() below normalizes this at every level before iterating.

Title                   : sdn-sense/sense-cisconx9-collection
Author                  : Justas Balcas
Email                   : juztas (at) gmail.com
@Copyright              : General Public License v3.0+
Date                    : 2026/09/15
"""
from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

import json
import re

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.sense.cisconx9.plugins.module_utils.network.cisconx9 import run_commands
from ansible_collections.sense.cisconx9.plugins.module_utils.network.cisconx9 import cisconx9_argument_spec, check_args
from ansible_collections.sense.cisconx9.plugins.module_utils.runwrapper import functionwrapper

_KNOWN_STATES = ("established", "idle", "active", "connect", "opensent", "openconfirm")


@functionwrapper
def normalizeBgpState(rawstate):
    """Normalize a vendor BGP FSM state string to the shared enum."""
    state = str(rawstate).lower()
    return state if state in _KNOWN_STATES else "unknown"


@functionwrapper
def asList(value):
    """NX-OS collapses a single-entry TABLE_x/ROW_x block to a bare dict
    instead of a list of one dict. Normalize both shapes to a list."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    return value


@functionwrapper
def iso8601DurationToSeconds(rawduration):
    """Convert an NX-OS ISO-8601-ish duration ('PT2M', 'PT2M47S', 'P1M25DT16H46M9S')
    to seconds. Returns None if unparsable. Only handles the D/H/M/S
    components actually seen in BGP output (no years handled)."""
    if not rawduration:
        return None
    match = re.match(
        r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", rawduration.strip()
    )
    if not match:
        return None
    days, hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


@functionwrapper
def buildSummaryCommand(vrf, iptype):
    """Build the NX9 'show bgp ... summary | json' command for a single AFI."""
    vrfclause = f"vrf {vrf} " if vrf else ""
    return f"show bgp {vrfclause}{iptype} unicast summary | json"


@functionwrapper
def buildNeighborDetailCommand(vrf, iptype, peer):
    """Build the NX9 single-peer detail command used for advertised counts.
    ASSUMPTION (unverified): vrf placement for this command form was not
    tested against a live non-default-VRF device."""
    vrfclause = f" vrf {vrf}" if vrf else ""
    prefix = "show ipv6 bgp neighbors" if iptype == "ipv6" else "show ip bgp neighbors"
    return f"{prefix} {peer}{vrfclause}"


@functionwrapper
def parseBgpSummaryJson(rawjson, iptype, peers):
    """Parse one AFI's 'summary | json' response, appending normalized peers."""
    try:
        data = json.loads(rawjson)
    except ValueError:
        return None
    vrfrows = asList(data.get("TABLE_vrf", {}).get("ROW_vrf"))
    vrfname = None
    for vrfrow in vrfrows:
        vrfname = vrfrow.get("vrf-name-out", vrfname)
        localasn = _toint(vrfrow.get("vrf-local-as"))
        for afrow in asList(vrfrow.get("TABLE_af", {}).get("ROW_af")):
            for safrow in asList(afrow.get("TABLE_saf", {}).get("ROW_saf")):
                for neighborrow in asList(safrow.get("TABLE_neighbor", {}).get("ROW_neighbor")):
                    peers.append({
                        "peer": neighborrow.get("neighborid"),
                        "iptype": iptype,
                        "local_asn": localasn,
                        "remote_asn": _toint(neighborrow.get("neighboras")),
                        "state": normalizeBgpState(neighborrow.get("state", "")),
                        "uptime_seconds": iso8601DurationToSeconds(neighborrow.get("time")),
                        "prefixes_received": _toint(neighborrow.get("prefixreceived")),
                        "prefixes_advertised": None,
                        "advertised_known": False,
                    })
    return vrfname


def _toint(value):
    """Best-effort int conversion, None on failure/absence."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@functionwrapper
def fillAdvertisedCount(module, vrf, peer):
    """Fetch and regex-parse the advertised-prefix count for one established
    peer via the single-peer plain-text detail command."""
    command = buildNeighborDetailCommand(vrf, peer["iptype"], peer["peer"])
    try:
        responses = run_commands(module, [command])
    except Exception:  # pylint: disable=broad-except
        return
    text = responses[0] if responses else ""
    acceptedmatch = re.search(r"(\d+)\s+accepted prefixes", text)
    sentmatch = re.search(r"(\d+)\s+sent prefixes", text)
    if acceptedmatch:
        peer["prefixes_received"] = int(acceptedmatch.group(1))
    if sentmatch:
        peer["prefixes_advertised"] = int(sentmatch.group(1))
        peer["advertised_known"] = True


@functionwrapper
def main():
    """main entry point for module execution"""
    argument_spec = {
        "vrf": {"type": "str", "default": ""},
        "type": {"type": "str", "default": "both", "choices": ["ipv4", "ipv6", "both"]},
        "detail": {"type": "bool", "default": True},
    }
    argument_spec.update(cisconx9_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    warnings = []
    check_args(module, warnings)

    vrf = module.params["vrf"]
    wanttype = module.params["type"]
    detail = module.params["detail"]
    wantafis = ["ipv4", "ipv6"] if wanttype == "both" else [wanttype]

    peers = []
    vrfname = None
    for iptype in wantafis:
        responses = run_commands(module, [buildSummaryCommand(vrf, iptype)])
        thisvrf = parseBgpSummaryJson(responses[0] if responses else "", iptype, peers)
        vrfname = vrfname or thisvrf

    if detail:
        for peer in peers:
            if peer["state"] == "established":
                fillAdvertisedCount(module, vrf, peer)

    bgp_summary = {"vrf": vrf or vrfname, "afi_checked": wantafis, "peers": peers}

    module.exit_json(changed=False, warnings=warnings, bgp_summary=bgp_summary)


if __name__ == "__main__":
    main()
