#!/usr/bin/env python3
"""dot-and-tilde's copies of the shared GitHub helpers are the same code.

bin/link_gh_issues.py and scripts/verify_github_write.py each carry their own
github_headers(), _after_https_scheme() and https_request(), and the
orchestrate plugin's scripts/ci_monitor/ci_monitor.py carries a third
_after_https_scheme(), so that each stays a single file with nothing to import
from outside its plugin. This test fails when any two copies stop being the
same code, so a change to one, a fix to the https-only check above all, reaches
the others. It reaches into orchestrate because both plugins live in this
repository and its CI runs every plugin's tests.

Docstrings are left out of the comparison: each copy's may say where it came
from. The helpers are copies of aunger/gallery-button-for-pixel-camera's
scripts/ci/prs-and-issues/, which this test cannot reach; a change there is
copied here by hand. So is the byline pattern, BYLINE_RE in
verify_github_write.py, which has no second copy here to compare.
"""

import ast
import os
import unittest

PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LINK = os.path.join(PLUGIN_ROOT, "bin", "link_gh_issues.py")
VERIFY = os.path.join(PLUGIN_ROOT, "scripts", "verify_github_write.py")
CI_MONITOR = os.path.join(
    PLUGIN_ROOT, "..", "orchestrate", "scripts", "ci_monitor", "ci_monitor.py"
)
# function name -> the files that carry a copy of it
COPIES = {
    "github_headers": (LINK, VERIFY),
    "_after_https_scheme": (LINK, VERIFY, CI_MONITOR),
    "https_request": (LINK, VERIFY),
}


def function_without_docstring(path, name):
    """Return the ast dump of the top-level function `name` in `path`, docstring removed."""
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:]
            return ast.dump(node)
    raise AssertionError("%s defines no top-level function %s" % (path, name))


class TestHelperCopies(unittest.TestCase):
    def test_every_copy_matches_the_first(self):
        for name, paths in COPIES.items():
            first = paths[0]
            for other in paths[1:]:
                with self.subTest(function=name, copy=os.path.relpath(other, PLUGIN_ROOT)):
                    self.assertEqual(
                        function_without_docstring(other, name),
                        function_without_docstring(first, name),
                        "%s in %s differs from bin/link_gh_issues.py's"
                        % (name, os.path.relpath(other, PLUGIN_ROOT)),
                    )


if __name__ == "__main__":
    unittest.main()
