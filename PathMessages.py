#!/usr/bin/env python
import json
import os
import pathspec
import re
import subprocess
import sys
import yaml

CONFIG_FILE = ".pathmessages.yaml"

def get_commit_pair():
    gitTarget = os.environ.get("GITHUB_BASE_REF")
    gitSource = os.environ.get("GITHUB_SHA")
    gitTarget = os.environ.get("LIFT_DST_SHA", gitTarget)
    gitSource = os.environ.get("LIFT_SRC_SHA", gitSource)
    return (gitTarget,gitSource)

def get_changed_files():
    (gitTarget,gitSource) = get_commit_pair()
    res = subprocess.run(["git", "diff", "--name-only", gitTarget + ".." + gitSource], capture_output=True);
    return res.stdout.decode('utf-8').splitlines()

# returns a list of rules with fileds:
#   paths
#   message
#   title
#   except
#       also_changed
def load_config(path):
    result = []
    with open(path) as hdl:
        entries = yaml.load(hdl, Loader=yaml.Loader)
        for entry in entries:
            this_result = { "title" : entry,
                            "message" : entries[entry]["message"],
                            "paths" : entries[entry]["paths"].splitlines(),
                            "except" : entries[entry].get("except",{})
                          }
            if this_result.get('except',{}).get('also_changed',None):
                this_result['except']['also_changed'] = this_result['except']['also_changed'].splitlines()
            result = result + [this_result]
    return result

def get_diff_line(file):
    (gitTarget,gitSource) = get_commit_pair()
    res = subprocess.run(["git", "diff", gitTarget + ".." + gitSource], capture_output=True);
    output_lines = res.stdout.decode('UTF-8') # .splitlines()
    matches = re.finditer("@@.*\+(.*),.*@@", output_lines)
    for match in matches:
        try:
            line = int(match.group(1))
            return (line+1)
        except:
            continue
    print("No diff line. Only binary files were changed?", file=stderr)
    return None

def make_match_string(rule,matches):
    matchStr = "(on patterns: " + ", ".join(rule['paths']) + ")"
    if len(matches) < 4:
       matchStr = "(on " + " ".join(matches) + ")"
    return matchStr

def applicable_exclusions(rule, changed_files):
    try:
        ex  = rule.get('except',{})
        also_changed = ex.get('also_changed',None)
        if also_changed:
            spec = pathspec.PathSpec.from_lines('gitwildmatch', also_changed)
            matches = list(spec.match_files(changed_files))
            return 0 < len(matches)
        else:
            return False
    except:
        return False

def apply_rule(rule, changed_files):
    spec = pathspec.PathSpec.from_lines('gitwildmatch', rule['paths'])
    matches = list(spec.match_files(changed_files))
    result = []
    if [] != matches:
        line = get_diff_line(matches[0])
        if line:
            matchStr = make_match_string(rule, matches)
            if not applicable_exclusions(rule, changed_files):
                result = [{ "file" : matches[0],
                            "line" : line,
                            "message": rule['message'] + " " + matchStr,
                            "type": rule['title']
                          }]
    return result

def emit_results(results):
    print(json.dumps(results))

def name():
    print("PathMessages")

def version():
    print("1")

def applicable():
    if (os.path.exists(CONFIG_FILE)):
        print("true")
    else:
        print("false")

def run():
    try:
        cfg = load_config(CONFIG_FILE)
    except:
        print("Could not load configuration. Check that it is a valid yaml", file=sys.stderr)
        sys.exit(1)

    changed_files = get_changed_files()
    results = []
    for rule in cfg:
        results = results + apply_rule(rule, changed_files)
    emit_results(results)

def main():
    if len(sys.argv) != 4:
        # Not running with the LiftV1 api. Just run the tool
        run()
    else:
        cmd = sys.argv[3]
        if 'run' == cmd:
            run()
        elif 'applicable' == cmd:
            applicable()
        elif 'name' == cmd:
            name()
        elif 'version' == cmd:
            version()
        else:
            print("invalid command", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    main()

