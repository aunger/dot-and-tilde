#!/usr/bin/env python3
"""The label tables the workflows pass to vcs-automation's actions agree.

Several of aunger/vcs-automation's label actions read the same table, and each
workflow passes its own copy as a `with:` input (vcs-automation's README,
"Label actions"). These tests fail when two copies differ, when the any-file
labels of label-by-files.yml are not kept out of the other tables, when the
orchestrate label protocol's labels are not where vcs-automation's README
section "The merge gate and orchestrate's labels" puts them, when the
vcs-automation pins differ, or when .claude/orchestrate.json does not match
the merge gate and test.yml.

Standard library only: a table is read as the JSON of a `key: |` block scalar,
the one form these workflows write their tables in, rather than by parsing the
YAML. Only the block of the key a test asks for is parsed, so other block
scalars, such as `run: |` steps, need not be JSON.
"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")
CONFIG = os.path.join(ROOT, ".claude", "orchestrate.json")
CHECK_CONFIG_DIR = os.path.join(ROOT, "plugins", "orchestrate", "scripts")

PROTOCOL_LABELS = {
    "orchestrate",
    "orchestrating",
    "verification needed",
    "verified",
    "changes requested",
    "changes done",
}
BLOCKING_LABELS = {"orchestrating", "verification needed", "changes requested", "changes done"}
PROTOCOL_SETS = [
    {"orchestrate", "orchestrating"},
    {"verification needed", "verified"},
    {"changes requested", "changes done"},
]
PROTOCOL_PREFIXES = {"c-a-", "c-r-"}
GATE_JOB_NAME = "Administrative merge holds (not failure)"


def read(name):
    with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as handle:
        return handle.read()


def table(name, key):
    """Parse the `key: |` block scalar in workflow *name* as JSON."""
    return parse_table(read(name), name, key)


def parse_table(text, name, key):
    """Parse the `key: |` block scalar in *text*, the workflow *name*, as JSON.

    Only *key*'s block is parsed; a block scalar under any other key, such as
    a `run: |` step, is skipped over.
    """
    lines = text.splitlines()
    bodies = []
    i = 0
    while i < len(lines):
        # A key may start a sequence entry (`- run: |`); its block is then
        # indented past the key's column, which the `- ` counts toward.
        match = re.fullmatch(r"( *(?:- +)*)([\w-]+): \|", lines[i])
        i += 1
        if not match:
            continue
        indent = len(match.group(1))
        body = []
        while i < len(lines) and (
            not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip(" ")) > indent
        ):
            body.append(lines[i])
            i += 1
        if match.group(2) == key:
            bodies.append(body)
    if not bodies:
        raise AssertionError("%s passes no %s block" % (name, key))
    if len(bodies) > 1:
        raise AssertionError("%s passes %s twice" % (name, key))
    try:
        return json.loads("\n".join(bodies[0]))
    except ValueError as error:
        raise AssertionError("%s: %s is not JSON: %s" % (name, key, error)) from error


def lowered(labels):
    return {label.lower() for label in labels}


def label_sets(sets):
    return sorted(sorted(lowered(s)) for s in sets)


class ParseTableTest(unittest.TestCase):
    TEXT = """\
steps:
  - run: |
      cat <<EOF
      wanted: |
        not JSON
      EOF
  - with:
      wanted: |
        {"a": [1, 2]}
      other: |
        also not JSON
"""

    def test_reads_only_the_key_asked_for(self):
        self.assertEqual(parse_table(self.TEXT, "w.yml", "wanted"), {"a": [1, 2]})

    def test_names_the_key_that_is_not_json(self):
        with self.assertRaisesRegex(AssertionError, r"\Aw\.yml: other is not JSON"):
            parse_table(self.TEXT, "w.yml", "other")

    def test_a_missing_key_fails(self):
        with self.assertRaisesRegex(AssertionError, r"\Aw\.yml passes no missing block\Z"):
            parse_table(self.TEXT, "w.yml", "missing")

    def test_a_repeated_key_fails(self):
        text = self.TEXT + "  - with:\n      wanted: |\n        []\n"
        with self.assertRaisesRegex(AssertionError, r"\Aw\.yml passes wanted twice\Z"):
            parse_table(text, "w.yml", "wanted")

    def test_a_key_inside_another_block_is_not_read(self):
        text = "run: |\n  wanted: |\n    oops\n"
        with self.assertRaisesRegex(AssertionError, r"\Aw\.yml passes no wanted block\Z"):
            parse_table(text, "w.yml", "wanted")

    def test_a_key_is_not_matched_as_a_suffix(self):
        text = "with:\n  not-wanted: |\n    oops\n"
        with self.assertRaisesRegex(AssertionError, r"\Aw\.yml passes no wanted block\Z"):
            parse_table(text, "w.yml", "wanted")


class SharedTablesTest(unittest.TestCase):
    def test_exclusive_tables_are_the_merge_gates(self):
        gate = "administrative-merge-holds.yml"
        for name in ("propagate-issue-labels.yml", "reconcile-issue-labels.yml"):
            with self.subTest(workflow=name):
                self.assertEqual(
                    label_sets(table(name, "exclusive-sets")),
                    label_sets(table(gate, "exclusive-sets")),
                )
                self.assertEqual(
                    lowered(table(name, "exclusive-prefixes")),
                    lowered(table(gate, "exclusive-prefixes")),
                )

    def test_excluded_labels_agree(self):
        self.assertEqual(
            lowered(table("propagate-issue-labels.yml", "excluded-labels")),
            lowered(table("reconcile-issue-labels.yml", "excluded-labels")),
        )

    def test_snooze_ladder_is_shared_and_exclusive(self):
        snooze = table("snooze-issues.yml", "snooze-labels")
        wake = table("wake-snoozed-issues.yml", "snooze-labels")
        self.assertEqual(
            {k.lower(): v for k, v in snooze.items()}, {k.lower(): v for k, v in wake.items()}
        )
        gate_sets = label_sets(table("administrative-merge-holds.yml", "exclusive-sets"))
        self.assertIn(sorted(lowered(snooze)), gate_sets)

    def test_any_file_labels_are_kept_out_of_the_other_tables(self):
        rules = table("label-by-files.yml", "rules")
        any_file = lowered(label for label, rule in rules.items() if rule["mode"] == "any-file")
        self.assertTrue(any_file)
        self.assertEqual(lowered(table("label-by-title.yml", "skip-on-pull-requests")), any_file)
        excluded = lowered(table("propagate-issue-labels.yml", "excluded-labels"))
        self.assertLessEqual(any_file, excluded)


class ProtocolLabelsTest(unittest.TestCase):
    def test_gate_blocks_on_the_protocols_labels(self):
        gate = table("administrative-merge-holds.yml", "blocking-labels")
        self.assertEqual(lowered(gate), BLOCKING_LABELS)

    def test_protocol_pairs_are_separate_sets(self):
        gate_sets = label_sets(table("administrative-merge-holds.yml", "exclusive-sets"))
        for pair in PROTOCOL_SETS:
            with self.subTest(pair=sorted(pair)):
                self.assertIn(sorted(pair), gate_sets)
        prefixes = lowered(table("administrative-merge-holds.yml", "exclusive-prefixes"))
        self.assertLessEqual(PROTOCOL_PREFIXES, prefixes)

    def test_protocol_labels_are_never_propagated(self):
        excluded = lowered(table("propagate-issue-labels.yml", "excluded-labels"))
        self.assertLessEqual(PROTOCOL_LABELS, excluded)

    def test_waking_removes_the_protocol_labels(self):
        self.assertEqual(
            lowered(table("wake-snoozed-issues.yml", "remove-on-wake")), PROTOCOL_LABELS
        )


class PinsTest(unittest.TestCase):
    def test_every_vcs_automation_action_is_pinned_to_one_release(self):
        uses = re.compile(r"uses: aunger/vcs-automation/[\w-]+@(\S+)(.*)")
        pins = set()
        for name in sorted(os.listdir(WORKFLOWS)):
            if not name.endswith(".yml"):
                continue
            for match in uses.finditer(read(name)):
                with self.subTest(workflow=name, pin=match.group(0)):
                    self.assertRegex(match.group(1), r"\A[0-9a-f]{40}\Z")
                    self.assertRegex(match.group(2), r"\A # v\d+\.\d+\.\d+\Z")
                pins.add((match.group(1), match.group(2)))
        self.assertEqual(len(pins), 1, sorted(pins))


class OrchestrateConfigTest(unittest.TestCase):
    def setUp(self):
        with open(CONFIG, encoding="utf-8") as handle:
            self.config = json.load(handle)

    def test_config_passes_the_plugins_check(self):
        sys.path.insert(0, CHECK_CONFIG_DIR)
        try:
            import check_config
        finally:
            sys.path.remove(CHECK_CONFIG_DIR)
        errors, _ = check_config.problems(self.config)
        self.assertEqual(errors, [])

    def test_ignored_check_regex_matches_the_gate_job(self):
        names = re.findall(r"^    name: (.+)$", read("administrative-merge-holds.yml"), re.M)
        self.assertEqual(names, [GATE_JOB_NAME])
        self.assertRegex(GATE_JOB_NAME, self.config["ignored_check_regex"])
        self.assertNotIn(GATE_JOB_NAME, self.config["named_checks"])

    def test_named_checks_cover_every_test_job(self):
        jobs = read("test.yml").split("\njobs:\n", 1)[1]
        ids = re.findall(r"^  ([\w-]+):$", jobs, re.M)
        self.assertTrue(ids)
        for job in ids:
            with self.subTest(job=job):
                self.assertIn(job, self.config["named_checks"])


if __name__ == "__main__":
    unittest.main()
