#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Three layers, read in this order:

    primitives  raw values -- colour ramps, the radius scale, blend ratios
    semantic    what each primitive is for -- palette maps, derived chrome
    components  the radii and densities the stylesheet asks for by name

A rule in a .qss template may only name a semantic or component token. If a
rule needs a value that is in neither, the value belongs in one of them, not
in the rule.
"""
