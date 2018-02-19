#!/usr/bin/env python3

import sys

from checkbox_tool import CheckboxTool


def main():
    tool = CheckboxTool()
    if len(sys.argv) != 2:
        raise SystemExit("missing argument: test plan!")
    tp = sys.argv[1]
    if tp not in tool.all_tps:
        raise SystemExit('"{}" test plan not found!'.format(tp))
    
    print(tool.annotated_tp(tp))

if __name__ == '__main__':
    main()
