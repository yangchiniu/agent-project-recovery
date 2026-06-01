#!/usr/bin/env python3
"""
Agent Project Recovery - CLI Tool

Usage:
    hermes-recover                    # Show recovery summary
    hermes-recover --json             # Output raw JSON
    hermes-recover set <field> <val>  # Set state field
    hermes-recover reset              # Reset state (use with caution)

License: MIT
"""

import argparse
import json
import sys
from pathlib import Path

from agent_recovery import ProjectRecovery, __version__


def main():
    parser = argparse.ArgumentParser(
        description="Agent Project Recovery CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hermes-recover                      Show recovery summary
  hermes-recover --json               Output raw JSON state
  hermes-recover --path ./state.yaml  Use custom state file
  hermes-recover set current_task "Implementing auth"
  hermes-recover set goal "Build MVP"
  hermes-recover reset                Reset state to empty
        """,
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    parser.add_argument(
        "--path",
        default="~/.hermes/project-state.yaml",
        help="Path to state file (default: ~/.hermes/project-state.yaml)",
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON state",
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # set command
    set_parser = subparsers.add_parser("set", help="Set a state field")
    set_parser.add_argument(
        "field",
        choices=["goal", "current_task", "next_task", "branch"],
        help="State field to set",
    )
    set_parser.add_argument(
        "value",
        nargs="?",
        default=None,
        help="Value to set (omit to clear)",
    )
    
    # reset command
    subparsers.add_parser("reset", help="Reset state to empty")
    
    args = parser.parse_args()
    
    # Initialize recovery
    recovery = ProjectRecovery(args.path)
    
    # Handle commands
    if args.command == "set":
        recovery.set_state(args.field, args.value, source="explicit_statement")
        if args.value:
            print(f"Set {args.field} = {args.value}")
        else:
            print(f"Cleared {args.field}")
    
    elif args.command == "reset":
        confirm = input("Are you sure you want to reset state? [y/N] ")
        if confirm.lower() == "y":
            recovery.reset()
            print("State reset to empty.")
        else:
            print("Cancelled.")
    
    else:
        # Default: show summary
        if args.output_json:
            print(recovery.export_json())
        else:
            summary = recovery.generate_recovery_summary()
            print(summary)
            
            # Show freshness
            age = recovery.get_age_seconds()
            if age < 3600:
                print(f"\n[Fresh: {int(age)}s ago]")
            elif age < 86400:
                hours = age / 3600
                print(f"\n[Stale: {hours:.1f}h ago]")
            else:
                days = age / 86400
                print(f"\n[Old: {days:.1f} days ago]")


if __name__ == "__main__":
    main()
