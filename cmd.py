#!/usr/bin/python

import sys
import repository

def print_help():
    print """Usage: 
ci <file>
co <file>
mkrepo <dir to create>
"""



def cmd_ci(args):
    pass

def cmd_mkrepo(args):
    repository.create_repository(args[0])

def main():
    if len(sys.argv) <= 1:
        print_help()
    elif sys.argv[1] == "ci":
        cmd_ci(sys.argv[2:])
    elif sys.argv[1] == "mkrepo":
        cmd_mkrepo(sys.argv[2:])
    else:
        print_help()
        return

if __name__ == "__main__":
    main()
