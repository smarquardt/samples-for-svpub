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
# If you have a video file containing a CAMM track, this script will upload
# it to Street View while also enabling blurring of faces and license plates.
#
# Be sure to insert your own key in _DEVELOPER_KEY before running this.

# Usage:
#
# $ python basic_uploader.py --video=<video file>

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
import json
import os
import urlparse
from apiclient import discovery
from apiclient import errors
import httplib2
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
import pycurl


_API_NAME = "streetviewpublish"
_API_VERSION = "v1"
_SCOPES = "https://www.googleapis.com/auth/streetviewpublish"
_APPLICATION_NAME = "Street View Publish API Sample"
_DEVELOPER_KEY = "YOUR-KEY-HERE"
_LABEL = "ALPHA_TESTER"
_DISCOVERY_SERVICE_URL = "https://%s.googleapis.com/$discovery/rest?version=%s"
_CLIENT_SECRETS_FILE = "streetviewpublish_config.json"
_REDIRECT_URI = "http://localhost:8080"

_parser = argparse.ArgumentParser(parents=[tools.argparser])
_parser.add_argument("--video", help="Full path of the video to upload")
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
  store = Storage(credential_path)
  credentials = store.get()
  if not credentials or credentials.invalid:
    flow = client.flow_from_clientsecrets(_CLIENT_SECRETS_FILE, _SCOPES)
    flow.redirect_uri = _REDIRECT_URI
    flow.user_agent = _APPLICATION_NAME
    if _flags:
      credentials = tools.run_flow(flow, store, _flags)
    else:
      credentials = tools.run(flow, store)
    print "Storing credentials to " + credential_path
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


def _publish(video_file):
  """Uploads a photo and returns the photo id.

  Args:
    video_file: Full path of the video to upload.
  Returns:
    The id if the upload was successful, otherwise None.
  """
  upload_url = _request_upload_url()
  _upload_video(video_file, upload_url)
  publish_response = _publish_sequence(upload_url)
  return publish_response


def _request_upload_url():
  """Requests an Upload URL from SV servers (step 1/3).

  Returns:
    The Upload URL.
  """
  credentials = _get_credentials()
  http = credentials.authorize(httplib2.Http())
  service = discovery.build(
      _API_NAME,
      _API_VERSION,
      developerKey=_DEVELOPER_KEY,
      discoveryServiceUrl=_get_discovery_service_url(),
      http=http)
  start_upload_response = service.photoSequence().startUpload(body={}).execute()
  upload_url = str(start_upload_response["uploadUrl"])
  return upload_url


def _upload_video(video_file, upload_url):
  """Uploads a the video bytes to SV servers (step 2/3).

  Args:
    video_file: Full path of the video to upload.
    upload_url: The upload URL returned by step 1.
  Returns:
    None.
  """
  credentials = _get_credentials()
  credentials.authorize(httplib2.Http())
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


def _publish_sequence(upload_url):
  """Publishes the content on Street View (step 3/3).

  Args:
    upload_url: The upload URL returned by step 1.
  Returns:
    The id if the upload was successful, otherwise None.
  """
  credentials = _get_credentials()
  http = credentials.authorize(httplib2.Http())
  service = discovery.build(
      _API_NAME,
      _API_VERSION,
      developerKey=_DEVELOPER_KEY,
      discoveryServiceUrl=_get_discovery_service_url(),
      http=http)
  publish_request = {"uploadReference": {"uploadUrl": upload_url}}
  publish_request["blurringOptions"] = {"blurFaces":"true","blurLicensePlates":"true"}
  try:
    publish_response = service.photoSequence().create(body=publish_request, inputType="VIDEO").execute()
    return publish_response["name"]
  except errors.HttpError as error:
    photo_response_error = json.loads(error.content)
    print photo_response_error
    return None


def main():
  if _flags.video is None:
    print "You must specify a video file."
    exit(1)

  if _flags.video is not None:
    sequence_id = _publish(_flags.video)
    output = "Sequence uploaded! Sequence id: " + sequence_id
    print output


if __name__ == "__main__":
  main()
