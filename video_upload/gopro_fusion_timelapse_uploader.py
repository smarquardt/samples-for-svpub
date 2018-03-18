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

# Script to upload GoPro Fusion timelapse photos using the Street View Publish API.
#
# This script will convert a series of timelapse photos into a photoSequence which
# also supports auto-connections and blurring.
#
# Because the script packages all the photos into a single file for uploading, it
# requires that you have as much free space as you have photos to upload.

# Usage:
#
# $ python gopro_fusion_timelapse_uploader.py \
#   --folder=<folder containing stitched photos> \
#   --blur (optional) \
#   --compress (optional) \
#   --key=<your developer key>

# Enabling compression will reduce the size of the uploaded file by about 9x but
# the compression itself may take a long time to run.  To decide whether to use
# compression you must consider the speed of your computer vs the speed of your
# internet connection.

# Requirements:
# This script requires the following libraries:
#
# - google-api-python-client
# - pycurl
#
# The libraries can be installed by running:
#
# $ pip install <library name>
#
# FFmpeg is required, follow instructions at https://trac.ffmpeg.org/wiki/CompilationGuide


import argparse
from datetime import datetime
from calendar import timegm
import time
import json
import os
import re
import urlparse
import gpxpy
import gpxpy.gpx
from apiclient import discovery
from apiclient import errors
import httplib2
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
import subprocess
import pycurl


API_NAME = "streetviewpublish"
API_VERSION = "v1"
SCOPES = "https://www.googleapis.com/auth/streetviewpublish"
APPLICATION_NAME = "Street View Publish API Python"
LABEL = "ALPHA_TESTER"
DISCOVERY_SERVICE_URL = "https://%s.googleapis.com/$discovery/rest?version=%s"
CLIENT_SECRETS_FILE = "streetviewpublish_config.json"
REDIRECT_URI = "http://localhost:8080"

parser = argparse.ArgumentParser(parents=[tools.argparser])
parser.add_argument("--folder", help="The folder you want to upload")
parser.add_argument("--blur", default=False, action='store_true', help="Enable auto-blurring")
parser.add_argument("--compress", default=False, action='store_true', help="Enable compression")
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
  store = Storage(credential_path)
  credentials = store.get()
  if not credentials or credentials.invalid:
    flow = client.flow_from_clientsecrets(CLIENT_SECRETS_FILE, _SCOPES)
    flow.redirect_uri = REDIRECT_URI
    flow.user_agent = APPLICATION_NAME
    if flags:
      credentials = tools.run_flow(flow, store, flags)
    else:
      credentials = tools.run(flow, store)
    print "Storing credentials to " + credential_path
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
  """Requests an Upload URL from SV servers (step 1/3).

  Returns:
    The Upload URL.
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
  """Uploads a the video bytes to SV servers (step 2/3).

  Args:
    photo_file: Full path of the photo to upload.
    upload_url: The upload URL returned by step 1.
  Returns:
    None.
  """
  credentials = get_credentials()
  credentials.authorize(httplib2.Http())
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
    response_code = curl.getinfo(pycurl.RESPONSE_CODE)
    curl.close()
  except pycurl.error:
    print("Error uploading file %s" % video_file)


def publish_video(upload_url, geodata, create_time):
  """Publishes the content on Street View (step 3/3).

  Args:
    upload_url: The upload URL returned by step 1.
    geodata: the rawGpsTimelines from extract_geodata
    create_time: the GPS timestamp of the first photo
  Returns:
    The id if the upload was successful, otherwise None.
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
  publish_request["captureTimeOverride"] = {"seconds": create_time}
  publish_request["gpsSource"] = "PHOTO_SEQUENCE"
  if flags.blur:
    publish_request["blurringOptions"] = {"blurFaces":"true","blurLicensePlates":"true"}
  publish_request.update({"rawGpsTimeline": geodata})
  try:
    publish_response = service.photoSequence().create(body=publish_request, inputType="VIDEO").execute()
    return publish_response["name"]
  except errors.HttpError as error:
    response_error = json.loads(error.content)
    print(response_error)
    return None


def extract_geodata(directory):
  rawGpsTimelines = []
  timestamp = 0
  createTime = 0
  for filename in sorted(os.listdir(directory)):
      if filename.endswith(".jpg"):
          rawGpsTimeline = {}
          current_file = os.path.join(directory, filename)
          print "Extracting EXIF from %s" % current_file
          if timestamp == 0:
              t = subprocess.check_output(["exiftool", "-gpstimestamp", current_file])
              t = t.split(":")
              t = t[1].strip() + ":" + t[2].strip() + ":" + t[3].strip()
              d = subprocess.check_output(["exiftool", "-gpsdatestamp", current_file])
              d = d.split(":")
              d = d[1].strip() + ":" + d[2].strip() + ":" + d[3].strip()
              p = '%Y:%m:%dT%H:%M:%S'
              timestring = str(d) + 'T' + str(t)
              timestamp = int(timegm(time.strptime(timestring, p)))
              createTime = timestamp
          else:
              timestamp = timestamp + 1
          lon = subprocess.check_output(["exiftool", "-gpslongitude", "-n", current_file])
          lon = lon.split(":")
          lon = lon[1].strip()
          lat = subprocess.check_output(["exiftool", "-gpslatitude", "-n", current_file])
          lat = lat.split(":")
          lat = lat[1].strip()
          alt = subprocess.check_output(["exiftool", "-gpsaltitude", "-n", current_file])
          alt = alt.split(":")
          alt = alt[1].strip()
          rawGpsTimeline["latLngPair"] = {
              "latitude": lat,
              "longitude": lon
          }
          rawGpsTimeline["altitude"] = alt
          rawGpsTimeline["gpsRecordTimestampUnixEpoch"] = {
              "seconds": timestamp
          }
          print rawGpsTimeline
          rawGpsTimelines.append(rawGpsTimeline)
  return (rawGpsTimelines, createTime)

def convert_video(directory):
  output_mp4 = "gopro_temp_video.mp4"
  first_file = os.listdir(directory)[1]
  split_file = first_file.split("_")
  file_pattern = directory + "/" + split_file[0] + "_" + split_file[1] + '_%06d.jpg'
  if flags.compress:
    subprocess.call(["ffmpeg", "-r", "1", "-i", file_pattern, "-c:v", "libx264", "-preset", "slower", "-crf", "18", "-r", "1", "-y", output_mp4])
  else:
    subprocess.call(["ffmpeg", "-r", "1", "-i", file_pattern, "-codec", "copy", "-r", "1", "-y", output_mp4])
  subprocess.call(["exiftool", '-make="GoPro"', '-model="GoPro Fusion"', "-overwrite_original", output_mp4])
  return output_mp4

def main():
  print "Configuration:"
  print "Folder: %s" % flags.folder
  print "Auto-blur: %s" % flags.blur
  print "Compression: %s" % flags.compress
  print "..."
  
  if flags.key is None:
    print "You must include your developer key."
    exit(1)

  if flags.folder is None:
    print "You must specify a folder."
    exit(1)

  if flags.folder is not None:
    print "Extracting GPS data from photos"
    geodata,create_time = extract_geodata(flags.folder)
    print "GPS extracted"
    print "Packaging photos into sequence"
    video_file = convert_video(flags.folder)
    print "Packaging complete"
    print "Preparing upload"
    upload_url = request_upload_url()
    print "Ready to upload"
    print "Uploading to Street View"
    upload_video(video_file, upload_url)
    print "Upload complete"
    print "Publishing..."
    sequence_id = publish_video(upload_url, geodata, create_time)
    print "Cleaning up temporary files..."
    subprocess.call(["rm", video_file])
    output = "Sequence published! Sequence id: %s" % sequence_id
    print output


if __name__ == '__main__':
  main()

