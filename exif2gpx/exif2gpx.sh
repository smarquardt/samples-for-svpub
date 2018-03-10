#!/bin/bash
#
# Copyright 2018 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
################################################################################
#
# Usage: put this in directory with JPEGs you want to extract from and then run ./exif2gpx.sh > file.gpx
# This script requires exiftool, get it here: https://www.sno.phy.queensu.ca/~phil/exiftool/install.html

echo '<?xml version="1.0" encoding="UTF-8"?><gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="https://github.com/smarquardt"><metadata><author></author></metadata><trk><trkseg>'
for file in *.JPG; do
	lat=$(exiftool -s -s -s -n -gpslatitude $file)
	lon=$(exiftool -s -s -s -n -gpslongitude $file)
	alt=$(exiftool -s -s -s -n -gpsaltitude $file)
	datestamp=$(exiftool -s -s -s -n -gpsdatestamp $file)
	timestamp=$(exiftool -s -s -s -n -gpstimestamp $file)
	year=$(cut -d':' -f1 <<<"$datestamp")
	month=$(cut -d':' -f2 <<<"$datestamp")
	date=$(cut -d':' -f3 <<<"$datestamp")
	echo "<trkpt lat=\"$lat\" lon=\"$lon\"><ele>$alt</ele><time>${year}-${month}-${date}T${timestamp}Z</time></trkpt>"
done
echo '</trkseg></trk></gpx>'
