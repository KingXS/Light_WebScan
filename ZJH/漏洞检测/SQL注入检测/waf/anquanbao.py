#!/usr/bin/env python2

"""
Copyright (c) 2006-2019 sqlmap developers (http://sqlmap.org/)
See the file 'LICENSE' for copying permission
"""

from lib.core.settings import WAF_ATTACK_VECTORS

__product__ = "Anquanbao Web Application Firewall (Anquanbao)"

def detect(get_page):
    retval = False

    for vector in WAF_ATTACK_VECTORS:
        page, headers, code = get_page(get=vector)
        retval |= code == 405 and any(_ in (page or "") for _ in ("/aqb_cc/error/", "hidden_intercept_time"))
        if retval:
            break

    return retval
