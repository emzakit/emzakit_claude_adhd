#!/bin/sh
# This repo's own launcher for macOS double-click; the work is in open-roadmap.sh, which runs the plugin's templates.
exec sh "$(dirname "$0")/open-roadmap.sh" "$@"
