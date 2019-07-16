"""
This is a sphinx extension to freeze your broken reference problems
when using ``nitpicky = True``.

The basic operation is:

1. Add this extension to your ``conf.py`` extensions.
2. Add ``missing_references_write_json = True`` to your ``conf.py``
3. Run sphinx-build. It will generate ``missing-references.json``
    next to your ``conf.py``.
4. Remove ``missing_references_write_json = True`` from your
    ``conf.py`` (or set it to ``False``)
5. Run sphinx-build again, and ``nitpick_ignore`` will
    contain all of the previously failed references.

"""

import json
import os.path

from docutils.utils import get_source_line


def record_missing_reference_handler(app, env, node, contnode):
    if not app.config.missing_references_write_json:
        # no-op when we are disabled.
        return

    if not hasattr(env, "missing_reference_record"):
        env.missing_reference_record = set()
    record = env.missing_reference_record

    domain = node["refdomain"]
    typ = node["reftype"]
    target = node["reftarget"]
    location = get_location(node, app)

    dtype = "{}:{}".format(domain, typ)

    # nitpick_ignore won't use the location field, but we store it anyways
    # to be helpful for those who want to make the documentation better.
    # It is included first so that the sort order of these records groups
    # local missing references.
    record.add((location, dtype, target))


def get_location(node, app):
    (path, line) = get_source_line(node)

    if path:

        basepath = os.path.abspath(os.path.join(app.confdir, ".."))
        path = os.path.relpath(path, start=basepath)

        if path.startswith(os.path.pardir):
            path = os.path.join("<external>", os.path.basename(path))

    else:
        path = "<unknown>"

    if line:
        line = str(line)
    else:
        line = ""

    return "%s:%s" % (path, line)


def save_missing_references_handler(app, exc):
    if not app.config.missing_references_write_json:
        # no-op when we are disabled.
        return

    path = os.path.join(app.confdir, "missing-references.json")

    records = [list(r) for r in app.env.missing_reference_record]
    records.sort()

    with open(path, "w") as stream:
        json.dump(records, stream, indent=2)


def prepare_missing_references_handler(app, config):
    if config.missing_references_write_json:
        return

    path = os.path.join(app.confdir, "missing-references.json")
    if not os.path.exists(path):
        return

    with open(path, "r") as stream:
        data = json.load(stream)

    # We store lists of (location, dtype, reference) in the JSON file for easy
    # cataloging, but nitpick_ignore only wants (dtype, referece) tuples to
    # ignore references.
    config.nitpick_ignore.extend((item[-2], item[-1]) for item in data)


def setup(app):
    app.add_config_value("missing_references_write_json", False, "env")

    app.connect("config-inited", prepare_missing_references_handler)
    app.connect("missing-reference", record_missing_reference_handler)
    app.connect("build-finished", save_missing_references_handler)
