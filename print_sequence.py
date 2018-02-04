#!/usr/bin/env python3
import sys

from checkbox_tool import CheckboxTool

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Missing argument: test plan!")
    tp = sys.argv[1]

    tool = CheckboxTool()
    if tp not in tool.all_tps:
        raise SystemExit('"{}" test plan not found!'.format(tp))
    for uid, kind, extras, annotations in tool.get_run_sequence(tp):
        print('{0:10}{1}{2: >130}'.format(kind, uid, extras).strip())


if __name__ == '__main__':
    main()
