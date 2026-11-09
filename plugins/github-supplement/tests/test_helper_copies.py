#!/usr/bin/env python3
"""The plugin's two copies of the shared GitHub helpers are the same code.

bin/link_gh_issues.py and scripts/verify_github_write.py each carry their own
github_headers(), _after_https_scheme() and https_request(), so that each stays
a single file with nothing to import from outside the plugin. This test fails
when the two copies stop being the same code, so a change to one reaches the
other.

Docstrings are left out of the comparison: each copy's may say where it came
from. Both are copies of aunger/gallery-button-for-pixel-camera's
scripts/ci/prs-and-issues/, which this test cannot reach; a change there is
copied here by hand.
"""

import ast
import os
import unittest

PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COPIES = (
    os.path.join(PLUGIN_ROOT, "bin", "link_gh_issues.py"),
    os.path.join(PLUGIN_ROOT, "scripts", "verify_github_write.py"),
)
SHARED = ("github_headers", "_after_https_scheme", "https_request")


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
    def test_the_two_copies_match(self):
        first, second = COPIES
        for name in SHARED:
            with self.subTest(function=name):
                self.assertEqual(
                    function_without_docstring(first, name),
                    function_without_docstring(second, name),
                    "%s differs between bin/link_gh_issues.py and scripts/verify_github_write.py"
                    % name,
                )


if __name__ == "__main__":
    unittest.main()
