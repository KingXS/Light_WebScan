#!/usr/bin/env python2

"""
Copyright (c) 2006-2019 sqlmap developers (http://sqlmap.org/)
See the file 'LICENSE' for copying permission
"""

__product__ = "Proventia Web Application Security (IBM)"

def detect(get_page):
    page, _, _ = get_page()
    if page is None:
        return False
    page, _, _ = get_page(url="/Admin_Files/")
    return page is None
