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

from collections import defaultdict
import json
import os.path

from docutils.utils import get_source_line
from sphinx.util import logging

logger = logging.getLogger(__name__)

def record_missing_reference_handler(app, env, node, contnode):
    if not app.config.missing_references_enabled:
        # no-op when we are disabled.
        return

    if not hasattr(env, "missing_reference_record"):
        env.missing_reference_record = defaultdict(set)
    record = env.missing_reference_record

    domain = node["refdomain"]
    typ = node["reftype"]
    target = node["reftarget"]
    location = get_location(node, app)

    dtype = "{}:{}".format(domain, typ)

    record[(dtype, target)].add(location)


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
    if not app.config.missing_references_enabled:
        # no-op when we are disabled.
        return

    json_path = os.path.join(app.confdir, 
                             app.config.missing_references_filename)

    records = app.env.missing_reference_record

    # Warn about any reference which is no longer missing.
    for ignored_reference, paths in app.env.missing_references_ignored_references.items():
        missing_reference_paths = records.get(ignored_reference, [])
        for ignored_refernece_path in paths:
            if ignored_refernece_path not in missing_reference_paths:
                dtype, target = ignored_reference
                msg = (f"Reference {dtype} {target} for {ignored_refernece_path} can be removed"
                       f" from {app.config.missing_references_filename}."
                        "It is no longer a missing reference in the docs.")
                logger.warning(msg,
                    location=ignored_refernece_path, type='ref', subtype=dtype)

    if app.config.missing_references_write_json:

        transformed_records = defaultdict(dict)

        for (dtype, target), paths in records.items():
            paths = list(paths)
            paths.sort()
            transformed_records[dtype][target] = paths

        with open(json_path, "w") as stream:
            json.dump(transformed_records, stream, indent=2)


def prepare_missing_references_handler(app):
    if not app.config.missing_references_enabled:
        # no-op when we are disabled.
        return

    app.env.missing_references_ignored_references = {}

    json_path = os.path.join(app.confdir, 
                             app.config.missing_references_filename)
    if not os.path.exists(json_path):
        return

    with open(json_path, "r") as stream:
        data = json.load(stream)

    ignored_references = {}
    for dtype, targets in data.items():
        for target, paths in targets.items():
            ignored_references[(dtype, target)] = paths
    
    app.env.missing_references_ignored_references = ignored_references

    if not app.config.missing_references_write_json:
        app.config.nitpick_ignore.extend(ignored_references.keys())


def setup(app):
    app.add_config_value("missing_references_enabled", True, "env")
    app.add_config_value("missing_references_write_json", False, "env")
    app.add_config_value("missing_references_filename",
                         "missing-references.json", "env")

    app.connect("builder-inited", prepare_missing_references_handler)
    app.connect("missing-reference", record_missing_reference_handler)
    app.connect("build-finished", save_missing_references_handler)
