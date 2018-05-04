# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ==============================================================================

# Script to upload a GoPro Fusion video using the Street View Publish API.
#
# Usage:
#
# $ python gopro_fusion_uploader.py \
#  --video=<stitched video file> \
#  --front=<front cam unstitched video file> \
#  --blur (optional) \
#  --key=<your developer key>

# Requirements:
# This script requires the following libraries:
#
# - google-api-python-client
# - gpxpy
# - pycurl
#
# The libraries can be installed by running:
#
# $ pip install <library name>
#
# FFmpeg is required, follow https://trac.ffmpeg.org/wiki/CompilationGuide
#
# This script also expects gopro2gpx to be in the same folder, which you can get
# from here and build: https://github.com/stilldavid/gopro-utils
#
# DO NOT TRIM THE START OF YOUR VIDEO OR IT WILL GET OUT OF SYNC!!!


import argparse
from calendar import timegm
import json
import os
from subprocess import call
import time
import urlparse
from apiclient import discovery
from apiclient import errors
import gpxpy
import gpxpy.gpx
import httplib2
from oauth2client import client
from oauth2client import file as googleapis_file
from oauth2client import tools
import pycurl

API_NAME = "streetviewpublish"
API_VERSION = "v1"
SCOPES = "https://www.googleapis.com/auth/streetviewpublish"
APPLICATION_NAME = "Street View Publish API Python"
LABEL = "ALPHA_TESTER"
DISCOVERY_SERVICE_URL = "https://%s.googleapis.com/$discovery/rest?version=%s"
CLIENT_SECRETS_FILE = "streetviewpublish_config.json"

parser = argparse.ArgumentParser(parents=[tools.argparser])
parser.add_argument("--video", help="Full path of the video to upload")
parser.add_argument("--front", help="Full path to front-facing unstitched video file")
parser.add_argument("--blur", default=False, action='store_true', help="Enable auto-blurring")
parser.add_argument("--exif", default=False, action='store_true', help="Write make/model to metadata")
parser.add_argument("--key", help="Your developer key")
flags = parser.parse_args()


def get_discovery_service_url():
  """Returns the discovery service url."""
  discovery_service_url = DISCOVERY_SERVICE_URL % (API_NAME, API_VERSION)
  if flags.key is not None:
    discovery_service_url += "&key=%s" % flags.key
  if LABEL is not None:
    discovery_service_url += "&labels=%s" % LABEL
  return discovery_service_url


def get_credentials():
  """Gets valid user credentials from storage.

  If nothing has been stored, or if the stored credentials are invalid,
  the OAuth2 flow is completed to obtain the new credentials.

  Returns:
      Credentials, the obtained credential.
  """
  home_dir = os.path.expanduser("~")
  credential_dir = os.path.join(home_dir, ".credentials")
  if not os.path.exists(credential_dir):
    os.makedirs(credential_dir)
  credential_path = os.path.join(credential_dir,
                                 "streetviewpublish_credentials.json")
  store = googleapis_file.Storage(credential_path)
  credentials = store.get()
  if not credentials or credentials.invalid:
    flow = client.flow_from_clientsecrets(CLIENT_SECRETS_FILE, SCOPES)
    flow.user_agent = APPLICATION_NAME
    credentials = tools.run_flow(flow, store, flags)
    print("Storing credentials to %s", credential_path)
  return credentials


def get_file_size(file_name):
  """Returns the size of the file."""
  with open(file_name, "r") as fh:
    fh.seek(0, os.SEEK_END)
    return fh.tell()


def get_headers(credentials, file_size, url):
  """Returns a list of header parameters in HTTP header format.

  Args:
    credentials: The credentials object returned from the get_credentials
      method.
    file_size: The size of the file returned from the get_file_size method.
    url: The upload url for the photo.

  Returns:
    A list of header parameters in HTTP header format. For example:
    Content-Type: image
  """
  parsed_url = urlparse.urlparse(url)
  host = parsed_url[1]
  headers = {
      "Content-Type": "video/mp4",
      "Authorization": "Bearer " + credentials.access_token,
      "X-Goog-Upload-Protocol": "raw",
      "X-Goog-Upload-Content-Length": str(file_size),
      "Host": host
  }
  return ["%s: %s" % (k, v) for (k, v) in headers.iteritems()]


def request_upload_url():
  """Requests Upload URL.

  Args:
    None.

  Returns:
    Upload URL.
  """
  credentials = get_credentials()
  http = credentials.authorize(httplib2.Http())
  service = discovery.build(
      API_NAME,
      API_VERSION,
      developerKey=flags.key,
      discoveryServiceUrl=get_discovery_service_url(),
      http=http)
  start_upload_response = service.photoSequence().startUpload(body={}).execute()
  upload_url = str(start_upload_response["uploadUrl"])
  return upload_url


def upload_video(video_file, upload_url):
  """Uploads video file to Street View via Upload URL.

  Args:
    video_file: The video file to upload.
    upload_url: The upload URL, provided by SV Publish API in step 1.

  Returns:
    None.
  """
  credentials = get_credentials()
  http = credentials.authorize(httplib2.Http())
  file_size = get_file_size(str(video_file))
  try:
    curl = pycurl.Curl()
    curl.setopt(pycurl.URL, upload_url)
    curl.setopt(pycurl.VERBOSE, 1)
    curl.setopt(pycurl.CUSTOMREQUEST, "POST")
    curl.setopt(pycurl.HTTPHEADER,
                get_headers(credentials, file_size, upload_url))
    curl.setopt(pycurl.INFILESIZE, file_size)
    curl.setopt(pycurl.READFUNCTION, open(str(video_file), "rb").read)
    curl.setopt(pycurl.UPLOAD, 1)
    curl.perform()
    curl.close()
  except pycurl.error:
    print "Error uploading file %s", video_file


def publish_sequence(upload_url, gpx_file):
  """Publishes sequence live on Street View.

  Args:
    upload_url: The upload URL, provided by SV Publish API in step 1.
    gpx_file: The GPX file, converted from GPMF by extract_gpmf().

  Returns:
    ID of published sequence, or None if unsuccessful.
  """
  credentials = get_credentials()
  http = credentials.authorize(httplib2.Http())
  service = discovery.build(
      API_NAME,
      API_VERSION,
      developerKey=flags.key,
      discoveryServiceUrl=get_discovery_service_url(),
      http=http)
  publish_request = {"uploadReference": {"uploadUrl": upload_url}}
  debug_output = '{"uploadReference": {"uploadUrl":"'
  debug_output += upload_url
  gpx_file = open(gpx_file, "r")
  gpx = gpxpy.parse(gpx_file)

  raw_gps_timelines = []
  create_time = 0
  repeated_timestamps = {}
  last_timestamp = 0
  # When GPMF is converted to GPX, subsecond precision is lost.  We should probably use a
  # different method of parsing GPMF, but for now we can just estimate the subsecond interval
  # by looking at repeated seconds.
  for track in gpx.tracks:
    for segment in track.segments:
      for point in segment.points:
        time_epoch = int(time.mktime(time.strptime(str(point.time), '%Y-%m-%d %H:%M:%S')))
        if time_epoch in repeated_timestamps:
          repeated_timestamps[time_epoch] = int(repeated_timestamps[time_epoch]) + 1
        else:
          repeated_timestamps[time_epoch] = 1
  
  counter = 0 
  for track in gpx.tracks:
    for segment in track.segments:
      for point in segment.points:
        time_epoch = int(time.mktime(time.strptime(str(point.time), '%Y-%m-%d %H:%M:%S')))
        if create_time == 0:
          create_time = time_epoch
        raw_gps_timeline = {}
        if int(time_epoch) == int(last_timestamp):
          # If a second has multiple entries, add nanoseconds
          counter = counter + 1
          nanos = int((float(counter) / float(repeated_timestamps[time_epoch])) * 1000000000)
        elif int(time_epoch) < int(last_timestamp):
          # Ignore entries where timestamps are out of order, as these may be erroneous
          continue
        else:
          counter = 0
          nanos = 0
        debug_output += '"rawGpsTimeline":{"latLngPair":{"latitude":'
        debug_output += str(point.latitude)
        debug_output += ',"longitude":'
        debug_output += str(point.longitude)
        debug_output += '},'
        raw_gps_timeline["latLngPair"] = {
            "latitude": point.latitude,
            "longitude": point.longitude
        }
        debug_output += '"altitude":'
        debug_output += str(point.elevation)
        debug_output += ','
        raw_gps_timeline["altitude"] = point.elevation
        
        raw_gps_timeline["gpsRecordTimestampUnixEpoch"] = {
            "seconds": time_epoch,
            "nanos" : nanos
        }
        debug_output += '"gpsRecordTimestampUnixEpoch":{"seconds":"'
        debug_output += str(time_epoch)
        debug_output += '","nanos":"'
        debug_output += str(nanos)
        debug_output += '"}}, '
        raw_gps_timelines.append(raw_gps_timeline)
        last_timestamp = time_epoch
  publish_request["captureTimeOverride"] = {"seconds": create_time}
  publish_request["gpsSource"] = "PHOTO_SEQUENCE"
  if flags.blur:
    publish_request["blurringOptions"] = {"blurFaces":"true","blurLicensePlates":"true"}
  debug_output += '"}, "captureTimeOverride":{"seconds":"'
  debug_output += str(create_time)
  debug_output += '"},'
  publish_request.update({"rawGpsTimeline": raw_gps_timelines})
  debug_output += '}'
  with open("metadata.json", "w") as json_file:
    json_file.write(debug_output)
  try:
    publish_response = service.photoSequence().create(body=publish_request, inputType="VIDEO").execute()
    return publish_response["name"]
  except errors.HttpError as error:
    photo_response_error = json.loads(error.content)
    print photo_response_error
    return None


def extract_gpmf(video_file):
  """Extracts GPMF data, converts to GPX, and saves a GPX file.

  Args:
    video_file: Full path of the video to upload.
  Returns:
    Filename of saved GPX file.
  """
  output_bin = "%s.bin" % video_file
  output_gpx = "%s.gpx" % video_file
  call(["ffmpeg", "-y", "-i", video_file, "-codec", "copy", "-map", "0:3", "-f", "rawvideo", output_bin])
  call(["./gopro2gpx", "-i", output_bin, "-o", output_gpx])
  call(["rm", output_bin])
  return output_gpx


def convert_video(video_file):
  """Converts video file to MP4, because Street View can't handle CFHD video format.

  Args:
    video_file: Full path of the video to upload.
  Returns:
    Filename of converted video file.
  """
  output_mp4 = "%s.mp4" % video_file
  call(["ffmpeg", "-i", video_file, "-c:v", "libx264", "-preset", "slower", "-crf", "18", "-r", "5", output_mp4])
  if flags.exif:
    call(["exiftool", "-make=GoPro", "-model=Fusion", "-makernotes:all=", "-overwrite_original", output_mp4])
  return output_mp4


def publish(video_file, gpx_file):
  """Uploads a photo and returns the photo id.

  Args:
    video_file: Full path of the video to upload.
    gpx_file: Full path of GPX file to parse.
  Returns:
    The id if the upload was successful, otherwise None.
  """
  upload_url = request_upload_url()
  upload_video(video_file, upload_url)
  publish_response = publish_sequence(upload_url, gpx_file)
  return publish_response


def main():
  print "Configuration:"
  print "Stitched Video: %s" % flags.video
  print "Unstitched Front Video: %s" % flags.front
  print "Auto-blur: %s" % flags.blur
  print "Update metadata: %s" % flags.exif
  print "..."
  
  if flags.key is None:
    print "You must include your developer key."
    exit(1)
  if flags.video is None:
    print "You must provide a video file."
    exit(1)
  if flags.video is not None and flags.front is not None:
    gpx_file = extract_gpmf(flags.front)
    video_file = convert_video(flags.video)
    sequence_id = publish(video_file, gpx_file)
    output = "Sequence uploaded! Sequence id: " + sequence_id
    # Clean up temp files. Comment these out if you want to see them.
    #call(["rm", video_file])
    #call(["rm", gpx_file])
    #call(["rm", "metadata.json"])
    print output


if __name__ == '__main__':
  main()
