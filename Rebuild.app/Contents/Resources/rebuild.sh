#!/bin/bash
osascript << 'AS'
tell application "Terminal"
    activate
    do script "bash /Users/nathanielregier/Developer/uplift/build.sh"
end tell
AS
