#!/bin/sh
# This repo's own launcher for macOS double-click; the work is in rebuild-dev-log.sh, which runs the plugin's templates.
exec sh "$(dirname "$0")/rebuild-dev-log.sh" "$@"
