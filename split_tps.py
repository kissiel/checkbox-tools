#!/usr/bin/env python3
import sys

from checkbox_tool import CheckboxTool

def main():
    if len(sys.argv) < 2:
        raise SystemExit("Missing argument: test plan(s)!")
    tp = sys.argv[1]

    tool = CheckboxTool()
    
    for tp in sys.argv[1:]:
        if tp not in tool.all_tps:
            raise SystemExit('"{}" test plan not found!'.format(tp))
        tool.split_tp(tp)


if __name__ == '__main__':
    main()
