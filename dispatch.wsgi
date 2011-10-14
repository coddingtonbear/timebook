#!/usr/bin/python
import os, sys, site

ROOT = os.path.dirname(__file__)
os.chdir(ROOT)

site.addsitedir("/usr/local/share/python-environments/timebook/lib/python2.6/site-packages")

# Add the path to your application, too.
sys.path.insert(0, os.path.join(ROOT, "timebook/"))

os.environ["PYTHON_EGG_CACHE"] = os.path.join(ROOT, "egg-cache/")

from timebook.web import app as application
