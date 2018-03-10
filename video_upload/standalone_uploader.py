
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

# Script to upload a photoSequence using the Street View Publish API.
#
# This script can be used when you have a standalone GPX track and a
# video, instead of a single video file with embedded geo-metadata.

# Usage:
#
# $ python standalone_uploader.py \
#   --video=<video file> \
#   --gpx=<gpx file> \
#   --time=<video starting time in seconds since epoch>
#
# Be sure to insert your key in _DEVELOPER_KEY before running this.

# Requirements:
# This script requires the following libraries:
#
# - google-api-python-client
# - pycurl
#
# The libraries can be installed by running:
#
# $ pip install <library name>


import argparse
from datetime import datetime
from calendar import timegm
import time
import json
import os
import re
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

_API_NAME = "streetviewpublish"
_API_VERSION = "v1"
_SCOPES = "https://www.googleapis.com/auth/streetviewpublish"
_APPLICATION_NAME = "Street View Publish API Python"
_DEVELOPER_KEY = "YOUR-KEY-HERE"
_LABEL = "ALPHA_TESTER"
_DISCOVERY_SERVICE_URL = "https://%s.googleapis.com/$discovery/rest?version=%s"
_CLIENT_SECRETS_FILE = "streetviewpublish_config.json"

_parser = argparse.ArgumentParser(parents=[tools.argparser])
_parser.add_argument("--video", help="Full path of the video to upload")
_parser.add_argument("--gpx", help="Full path of the gpx file to upload")
_parser.add_argument("--time", help="Video start time in seconds since epoch")
_flags = _parser.parse_args()


def _get_discovery_service_url():
  """Returns the discovery service url."""
  discovery_service_url = _DISCOVERY_SERVICE_URL % (_API_NAME, _API_VERSION)
  if _DEVELOPER_KEY is not None:
    discovery_service_url += "&key=%s" % _DEVELOPER_KEY
  if _LABEL is not None:
    discovery_service_url += "&labels=%s" % _LABEL
  return discovery_service_url


def _get_credentials():
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
    flow = client.flow_from_clientsecrets(_CLIENT_SECRETS_FILE, _SCOPES)
    flow.user_agent = _APPLICATION_NAME
    credentials = tools.run_flow(flow, store, _flags)
    print("Storing credentials to %s", credential_path)
  return credentials


def _get_file_size(file_name):
  """Returns the size of the file."""
  with open(file_name, "r") as fh:
    fh.seek(0, os.SEEK_END)
    return fh.tell()


def _get_headers(credentials, file_size, url):
  """Returns a list of header parameters in HTTP header format.

  Args:
    credentials: The credentials object returned from the _get_credentials
      method.
    file_size: The size of the file returned from the _get_file_size method.
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


def _upload_video(video_file, gpx_file, create_time, service, credentials):
  """Uploads a photo and returns the photo id.

  Args:
    video_file: Full path of the video to upload.
    gpx_file: Full path of the gpx file to upload.
    create_time: Creation time of the video, in seconds since epoch.
    service: the Street View Publish API service.
    credentials: The credentials object returned from the _get_credentials
      method.
  Returns:
    The id if the upload was successful, otherwise None.
  """
  # 1. Request upload URL
  start_upload_response = service.photoSequence().startUpload(body={}).execute()
  upload_url = str(start_upload_response["uploadUrl"])

  # 2. Upload video bytes
  file_size = _get_file_size(str(video_file))
  try:
    curl = pycurl.Curl()
    curl.setopt(pycurl.URL, upload_url)
    curl.setopt(pycurl.VERBOSE, 1)
    curl.setopt(pycurl.CUSTOMREQUEST, "POST")
    curl.setopt(pycurl.HTTPHEADER,
                _get_headers(credentials, file_size, upload_url))
    curl.setopt(pycurl.INFILESIZE, file_size)
    curl.setopt(pycurl.READFUNCTION, open(str(video_file), "rb").read)
    curl.setopt(pycurl.UPLOAD, 1)

    curl.perform()
    response_code = curl.getinfo(pycurl.RESPONSE_CODE)
    curl.close()
  except pycurl.error:
    print("Error uploading file %s", video_file)

  if response_code is not 200:
    print("Error uploading file %s", video_file)

  # 3. Publish sequence
  publish_request = {"uploadReference": {"uploadUrl": upload_url}}
  publish_request["captureTimeOverride"] = {"seconds": create_time}

  gpx_file = open(gpx_file, 'r')
  gpx = gpxpy.parse(gpx_file)

  rawGpsTimelines = []
  for track in gpx.tracks:
    for segment in track.segments:
      for point in segment.points:
        time_epoch = timegm(time.strptime(str(point.time), '%Y-%m-%d %H:%M:%S'))
        rawGpsTimeline = {}
        rawGpsTimeline["latLngPair"] = {
            "latitude": point.latitude,
            "longitude": point.longitude
        }
        rawGpsTimeline["altitude"] = point.elevation
        rawGpsTimeline["gpsRecordTimestampUnixEpoch"] = {
            "seconds": time_epoch
        }
        rawGpsTimelines.append(rawGpsTimeline)
  publish_request.update({"rawGpsTimeline": rawGpsTimelines})
  try:
    publish_response = service.photoSequence().create(body=publish_request, inputType="VIDEO").execute()
    return publish_response["name"]
  except errors.HttpError as error:
    photo_response_error = json.loads(error.content)
    print(photo_response_error)
    return None


def main():
  if _flags.video is None or _flags.gpx is None:
    print("You must provide a video file and a gpx file.")
    exit(1)

  create_time = 0
  if _flags.time is not None:
    create_time = _flags.time
  else:
    # If this is a file from Insta360 then the timestamp is in the filename
    regex = r".*_([0-9]{4})_([0-9]{2})_([0-9]{2})_([0-9]{2})_([0-9]{2})_([0-9]{2}).*"
    matches = re.match(regex,_flags.video)
    if matches is not None:
      file_timestamp = matches.group(1) + "-" + matches.group(2) + "-" + matches.group(3) + " " + matches.group(4) + ":" + matches.group(5) + ":" + matches.group(6)
      time_epoch = timegm(time.strptime(file_timestamp, '%Y-%m-%d %H:%M:%S'))
      create_time = time_epoch
    else:
      print("You must either pass the time argument or have the time contained in the video filename in the format YYYY_MM_DD_HH_MM_SS")
      exit(1)

  credentials = _get_credentials()
  http = credentials.authorize(httplib2.Http())

  service = discovery.build(
      _API_NAME,
      _API_VERSION,
      developerKey=_DEVELOPER_KEY,
      discoveryServiceUrl=_get_discovery_service_url(),
      http=http)

  if _flags.video is not None:
    sequence_id = _upload_video(_flags.video, _flags.gpx, create_time, service, credentials)
    output = "Sequence uploaded! Sequence id: " + sequence_id
    print(output)


if __name__ == '__main__':
  main()
