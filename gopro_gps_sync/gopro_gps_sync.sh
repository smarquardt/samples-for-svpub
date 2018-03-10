#!/bin/bash
#
# Copyright 2009 Google Inc.
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
# This script can be used to pass GPS metadata from source images to
# stitched images if the GoPro Fusion Studio is not passing metadata through
# properly. The first argument is the first image in the series of output
# stitched images from Studio.  The second argument is the first image in the
# series of unstitched original images from the front-facing camera.
#
# Usage: ./gopro_gps_sync.sh MULTISHOT_0500_000000.jpg GF040500.JPG

stitched=$1
unstitched=$2

stitched_dir="${stitched%/*}"
stitched_file="${stitched##*/}"
unstitched_dir="${unstitched%/*}"
unstitched_file="${unstitched##*/}"

stitched_f1=$(echo $stitched_file | cut -d'_' -f1)
stitched_f2=$(echo $stitched_file | cut -d'_' -f2)
stitched_firstpart="${stitched_f1}_${stitched_f2}"
stitched_lastpart=$(echo $stitched_file | cut -d'_' -f3)
stitched_counter="${stitched_lastpart%%.*}"

unstitched_firstpart="${unstitched_file%%.*}"
unstitched_counter="${unstitched_firstpart:2}"

i=0
cd "${stitched_dir}"
for file in ${stitched_firstpart}_*.jpg; do
	echo "Processing $file"
	source_num=$(printf "%06d\n" $((10#$unstitched_counter + i )))
	source="${unstitched_dir}/GF${source_num}.JPG"
	exiftool -overwrite_original_in_place -tagsFromFile $source $file
	i=$(($i + 1))
done
cd -

echo "Processed $i files."
