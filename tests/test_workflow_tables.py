#!/usr/bin/env python3
"""The label tables the workflows pass to vcs-automation's actions agree.

Several of aunger/vcs-automation's label actions read the same table, and each
workflow passes its own copy as a `with:` input (vcs-automation's README,
"Label actions"). These tests fail when two copies differ, when the any-file
labels of label-by-files.yml are not kept out of the other tables, when the
orchestrate label protocol's labels are not where vcs-automation's README
section "The merge gate and orchestrate's labels" puts them, when the
vcs-automation pins differ, or when .claude/orchestrate.json does not match
the merge gate and the check names test.yml and codeql.yml produce.

Standard library only: a table is read as the JSON of a `key: |` block scalar,
the one form these workflows write their tables in, rather than by parsing the
YAML.
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


def tables(name):
    """Map each `key: |` block scalar in workflow *name* to its value parsed as JSON."""
    lines = read(name).splitlines()
    found = {}
    i = 0
    while i < len(lines):
        match = re.fullmatch(r"( *)([\w-]+): \|", lines[i])
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
        key = match.group(2)
        if key in found:
            raise AssertionError("%s passes %s twice" % (name, key))
        try:
            found[key] = json.loads("\n".join(body))
        except ValueError as error:
            raise AssertionError("%s: %s is not JSON: %s" % (name, key, error)) from error
    return found


def check_names(text):
    """The check names the jobs of workflow *text* report to GitHub.

    A job reports its `name:` where one is set and its id otherwise. A name
    that interpolates one `matrix.<key>` is expanded once per `- <key>: value`
    entry of the job's `matrix: include:` list; any other expression in a name
    is refused, since this reading cannot evaluate it.
    """
    jobs = text.split("\njobs:\n", 1)[1]
    names = []
    for match in re.finditer(r"^  ([\w-]+):\n((?:(?:    .*)?\n)*)", jobs + "\n", re.M):
        job, body = match.groups()
        named = re.search(r"^    name: (.+)$", body, re.M)
        name = named.group(1).strip() if named else job
        expression = re.fullmatch(r"(.*)\$\{\{ matrix\.([\w-]+) \}\}(.*)", name)
        if expression:
            before, key, after = expression.groups()
            values = re.findall(r"^ +- %s: (\S+)$" % re.escape(key), body, re.M)
        else:
            before, after, values = name, "", [""]
        if "${{" in before + after or not values:
            raise AssertionError("cannot expand the check name %r of job %s" % (name, job))
        names.extend(before + value + after for value in values)
    if not names:
        raise AssertionError("no jobs found")
    return names


def lowered(labels):
    return {label.lower() for label in labels}


def label_sets(sets):
    return sorted(sorted(lowered(s)) for s in sets)


class SharedTablesTest(unittest.TestCase):
    def test_exclusive_tables_are_the_merge_gates(self):
        gate = tables("administrative-merge-holds.yml")
        for name in ("propagate-issue-labels.yml", "reconcile-issue-labels.yml"):
            other = tables(name)
            with self.subTest(workflow=name):
                self.assertEqual(
                    label_sets(other["exclusive-sets"]), label_sets(gate["exclusive-sets"])
                )
                self.assertEqual(
                    lowered(other["exclusive-prefixes"]), lowered(gate["exclusive-prefixes"])
                )

    def test_excluded_labels_agree(self):
        self.assertEqual(
            lowered(tables("propagate-issue-labels.yml")["excluded-labels"]),
            lowered(tables("reconcile-issue-labels.yml")["excluded-labels"]),
        )

    def test_snooze_ladder_is_shared_and_exclusive(self):
        snooze = tables("snooze-issues.yml")["snooze-labels"]
        wake = tables("wake-snoozed-issues.yml")["snooze-labels"]
        self.assertEqual(
            {k.lower(): v for k, v in snooze.items()}, {k.lower(): v for k, v in wake.items()}
        )
        gate_sets = label_sets(tables("administrative-merge-holds.yml")["exclusive-sets"])
        self.assertIn(sorted(lowered(snooze)), gate_sets)

    def test_any_file_labels_are_kept_out_of_the_other_tables(self):
        rules = tables("label-by-files.yml")["rules"]
        any_file = lowered(label for label, rule in rules.items() if rule["mode"] == "any-file")
        self.assertTrue(any_file)
        self.assertEqual(
            lowered(tables("label-by-title.yml")["skip-on-pull-requests"]), any_file
        )
        excluded = lowered(tables("propagate-issue-labels.yml")["excluded-labels"])
        self.assertLessEqual(any_file, excluded)


class ProtocolLabelsTest(unittest.TestCase):
    def test_gate_blocks_on_the_protocols_labels(self):
        gate = tables("administrative-merge-holds.yml")
        self.assertEqual(lowered(gate["blocking-labels"]), BLOCKING_LABELS)

    def test_protocol_pairs_are_separate_sets(self):
        gate_sets = label_sets(tables("administrative-merge-holds.yml")["exclusive-sets"])
        for pair in PROTOCOL_SETS:
            with self.subTest(pair=sorted(pair)):
                self.assertIn(sorted(pair), gate_sets)
        prefixes = lowered(tables("administrative-merge-holds.yml")["exclusive-prefixes"])
        self.assertLessEqual(PROTOCOL_PREFIXES, prefixes)

    def test_protocol_labels_are_never_propagated(self):
        excluded = lowered(tables("propagate-issue-labels.yml")["excluded-labels"])
        self.assertLessEqual(PROTOCOL_LABELS, excluded)

    def test_waking_removes_the_protocol_labels(self):
        self.assertEqual(
            lowered(tables("wake-snoozed-issues.yml")["remove-on-wake"]), PROTOCOL_LABELS
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

    def test_named_checks_are_the_check_names_of_test_and_codeql(self):
        produced = check_names(read("test.yml")) + check_names(read("codeql.yml"))
        self.assertCountEqual(self.config["named_checks"], produced)


class CheckNamesTest(unittest.TestCase):
    def test_job_without_a_name_reports_its_id(self):
        self.assertEqual(check_names("on: push\njobs:\n  build:\n    runs-on: x\n"), ["build"])

    def test_name_overrides_the_id(self):
        text = "on: push\njobs:\n  build:\n    name: Build it\n    runs-on: x\n"
        self.assertEqual(check_names(text), ["Build it"])

    def test_matrix_include_expands_the_name(self):
        text = (
            "on: push\n"
            "jobs:\n"
            "  analyze:\n"
            "    name: Analyze (${{ matrix.language }})\n"
            "    strategy:\n"
            "      matrix:\n"
            "        include:\n"
            "          - language: actions\n"
            "            build-mode: none\n"
            "\n"
            "          - language: python\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "  next:\n"
            "    runs-on: x\n"
        )
        self.assertEqual(
            check_names(text), ["Analyze (actions)", "Analyze (python)", "next"]
        )

    def test_an_unexpandable_name_is_refused(self):
        text = "on: push\njobs:\n  build:\n    name: Build ${{ github.ref }}\n"
        with self.assertRaises(AssertionError):
            check_names(text)


if __name__ == "__main__":
    unittest.main()
