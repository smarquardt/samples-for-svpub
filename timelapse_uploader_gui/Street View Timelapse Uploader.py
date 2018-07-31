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
# $ python gopro_fusion_timelapse_uploader.py

# Enabling compression will reduce the size of the uploaded file by 5-10x but
# the compression itself may take a long time to run.  To decide whether to use
# compression you must consider the speed of your computer vs the speed of your
# internet connection.  Compression time can easily be 10x video length or more.


from datetime import datetime
from calendar import timegm
import time
import json
import os
import re
import sys
import urlparse
import gpxpy
import gpxpy.gpx
from apiclient import discovery
from apiclient import errors
import httplib2
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
import exiftool
import ffmpeg
import requests
import subprocess
import wx

KEY = "REPLACE-WITH-YOUR-KEY"

API_NAME = "streetviewpublish"
API_VERSION = "v1"
SCOPES = "https://www.googleapis.com/auth/streetviewpublish"
APPLICATION_NAME = "Street View Publish API Sample"
LABEL = "ALPHA_TESTER"
DISCOVERY_SERVICE_URL = "https://%s.googleapis.com/$discovery/rest?version=%s"
CLIENT_SECRETS_FILE = "streetviewpublish_config.json"
REDIRECT_URI = "http://localhost:8080"
COMPRESS = False
os.environ['PATH'] = '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin' + os.environ['PATH']


def get_discovery_service_url():
  """Returns the discovery service url."""
  discovery_service_url = DISCOVERY_SERVICE_URL % (API_NAME, API_VERSION)
  discovery_service_url += "&key=%s" % KEY
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
    flow = client.flow_from_clientsecrets(CLIENT_SECRETS_FILE, SCOPES)
    flow.redirect_uri = REDIRECT_URI
    flow.user_agent = APPLICATION_NAME
    credentials = tools.run(flow, store)
    print "Storing credentials to " + credential_path
  return credentials


def get_file_size(file_name):
  """Returns the size of the file."""
  with open(file_name, "r") as fh:
    fh.seek(0, os.SEEK_END)
    return fh.tell()
    
def xfer_progress(total_to_download, total_downloaded, total_to_upload, total_uploaded):
    """Outputs transfer progress for PyCurl.

    Args:
      total_to_download: Total bytes to download
      total_downloaded: Total bytes downloaded
      total_to_upload: Total bytes to upload
      total_uploaded: Total bytes uploaded

    Returns: None
    """
    if total_to_upload:
      if total_uploaded > 0:
        percent_completed = round(float(total_uploaded)/float(total_to_upload), ndigits=2)*100
      else:
        percent_completed = 0
      upload_mb = round(total_uploaded/1000000, ndigits=2)
      total_mb = round(total_to_upload/1000000, ndigits=2)
      sys.stdout.write("Uploaded %s MB of %s MB (%s%%)\r" %(upload_mb, total_mb, percent_completed)),
      sys.stdout.flush()
      frame.line2.SetLabel("Uploaded %s MB of %s MB (%s%%)\r" %(upload_mb, total_mb, percent_completed))


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
  frame.line2.SetLabel("Requesting upload URL (Step 1/3)")
  credentials = get_credentials()
  http = credentials.authorize(httplib2.Http())
  service = discovery.build(
      API_NAME,
      API_VERSION,
      developerKey=KEY,
      discoveryServiceUrl=get_discovery_service_url(),
      http=http)
  start_upload_response = service.photoSequence().startUpload(body={}).execute()
  upload_url = str(start_upload_response["uploadUrl"])
  status = "Upload URL: " + upload_url
  frame.line2.SetLabel(status)
  return upload_url


def upload_video(video_file, upload_url):
  """Uploads a the video bytes to SV servers (step 2/3).

  Args:
    photo_file: Full path of the photo to upload.
    upload_url: The upload URL returned by step 1.
  Returns:
    None.
  """
  parsed_url = urlparse.urlparse(upload_url)
  host = parsed_url[1]
  credentials = get_credentials()
  credentials.authorize(httplib2.Http())
  file_size = get_file_size(str(video_file))
  try:
      h = {"Authorization": "Bearer " + credentials.access_token,
                 "Content-Type": "video/mp4",
                  "X-Goog-Upload-Protocol": "raw",
                  "X-Goog-Upload-Content-Length": str(file_size),
                  "Host": host
                 }
      with open(video_file,"rb") as upload_target:
          r = requests.post(upload_url,headers=h,data=upload_target)
  except Exception as error_message:
      print(error_message)


def publish_video(upload_url, geodata, create_time):
  """Publishes the content on Street View (step 3/3).

  Args:
    upload_url: The upload URL returned by step 1.
    geodata: the rawGpsTimelines from extract_geodata
    create_time: the GPS timestamp of the first photo
  Returns:
    The id if the upload was successful, otherwise None.
  """
  frame.line2.SetLabel("Publishing on Street View (Step 3/3)")
  credentials = get_credentials()
  http = credentials.authorize(httplib2.Http())
  service = discovery.build(
      API_NAME,
      API_VERSION,
      developerKey=KEY,
      discoveryServiceUrl=get_discovery_service_url(),
      http=http)
  publish_request = {"uploadReference": {"uploadUrl": upload_url}}
  publish_request["captureTimeOverride"] = {"seconds": create_time}
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
              with exiftool.ExifTool() as et:
                  t = et.get_tag('gpstimestamp',current_file)
                  d = et.get_tag('gpsdatestamp',current_file)
              p = '%Y:%m:%dT%H:%M:%S'
              timestring = str(d) + 'T' + str(t)
              timestamp = int(timegm(time.strptime(timestring, p)))
              createTime = timestamp
          else:
              # For simplicity, we just increment each photo by one second so we don't
              # actually need to determine the original framerate.  As long as we also
              # encode the video at 1fps, this is completely fine.
              timestamp = timestamp + 1
          lon = subprocess.check_output(["exiftool", "-gpslongitude", "-n", current_file])
          with exiftool.ExifTool() as et:
              lon = et.get_tag('gpslongitude',current_file)
              lat = et.get_tag('gpslatitude',current_file)
              alt = et.get_tag('gpsaltitude',current_file)
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
  output_mp4 = "/tmp/sv_temp_video.mp4"
  first_file = os.listdir(directory)[1]
  split_file = first_file.split("_")
  file_pattern = directory + "/" + split_file[0] + "_" + split_file[1] + '_%06d.jpg'
  if COMPRESS:
    stream = ffmpeg.input(file_pattern,r=1)
    stream = ffmpeg.output(stream, output_mp4, vcodec='libx264', preset='slower', crf='18', r=1)
    ffmpeg.run(stream)
  else:
    stream = ffmpeg.input(file_pattern,r=1)
    stream = ffmpeg.output(stream, output_mp4, codec='copy')
    ffmpeg.run(stream)
  return output_mp4

def publish(folder):
  print "Configuration:"
  print "Folder: %s" % folder
  print "Compression: %s" % COMPRESS
  print "..."
  
  print "Extracting GPS data from photos"
  geodata,create_time = extract_geodata(folder)
  print "GPS extracted"
  print "Packaging photos into sequence"
  video_file = convert_video(folder)
  print "Packaging complete"
  print "Preparing upload"
  upload_url = request_upload_url()
  print "Upload target: %s" % upload_url
  print "Ready to upload"
  print "Uploading to Street View"
  upload_video(video_file, upload_url)
  print "\nUpload complete"
  print "Publishing..."
  sequence_id = publish_video(upload_url, geodata, create_time)
  print "Cleaning up temporary files..."
  subprocess.call(["rm", video_file])
  output = "Sequence published! Sequence id: %s" % sequence_id
  print output
  frame.line2.SetLabel(output)


class MainFrame(wx.Frame):
    def __init__(self,parent,title):
        super(MainFrame, self).__init__(parent, title=title, size=(1000,250))
        self.InitUI()
        self.Centre()
        
    def InitUI(self):
        menubar = wx.MenuBar()
        fileMenu = wx.Menu()
        fileItem = fileMenu.Append(wx.ID_EXIT, 'Quit', 'Quit application')
        menubar.Append(fileMenu, '&File')
        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.OnQuit, fileItem)

        self.SetTitle('Street View Upload Tool for Timelapse Photos')
        
        self.panel = wx.Panel(self)
        self.font = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT)
        self.font.SetPointSize(12)
        self.boldfont = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT)
        self.boldfont.SetPointSize(14)
        self.boldfont.SetWeight(wx.BOLD)
        
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.line1 = wx.StaticText(self.panel, label="Street View upload tool for geotagged timelapse photos")   
        self.line1.SetFont(self.boldfont)
        self.line2 = wx.StaticText(self.panel, label="Select a folder to upload:")   
        self.line2.SetFont(self.font)
        self.file_picker_button = wx.Button(self.panel, label="Choose folder")
        self.file_picker_button.SetFont(self.font)
        self.file_publish_button = wx.Button(self.panel, label="Publish")
        self.file_publish_button.SetFont(self.font)
        self.info_panel = wx.StaticText(self.panel, label="")
        self.info_panel.SetFont(self.font)
        
        self.vbox.Add(self.line1, wx.ID_ANY, wx.EXPAND | wx.ALL, 20)
        self.vbox.Add((1,1))
        self.vbox.Add(self.line2, wx.ID_ANY, wx.EXPAND | wx.ALL, 20)
        self.vbox.Add(self.file_picker_button, wx.ID_ANY, wx.EXPAND | wx.ALL, 20)
        self.vbox.Add(self.file_publish_button, wx.ID_ANY, wx.EXPAND | wx.ALL, 20)
        self.vbox.Add(self.info_panel, wx.ID_ANY, wx.EXPAND | wx.ALL, 20)
        self.panel.SetSizer(self.vbox)

        # Set event handlers
        self.file_picker_button.Bind(wx.EVT_BUTTON, self.OnPickerButton)
        self.file_publish_button.Hide()

    def OnQuit(self, e):
            self.Close()
            
    def OnPickerButton(self, event):
        dlg = wx.DirDialog(None, "Choose a folder", style=wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK: 
          path = dlg.GetPath()  
        dlg.Destroy()
        
        try:
          path
        except NameError:
          # no valid file was picked
          print "File picker exited with no valid file selected"
        else:
          result_label = "Ready to upload " + path
          self.line2.SetLabel(result_label)
          self.file_publish_button.Bind(wx.EVT_BUTTON, self.OnPublishButton)
          self.file_publish_button.Show()
          self.Layout()
          self.vbox.Layout()
          self.upload_target = path

    def OnPublishButton(self,event):
        self.file_picker_button.Destroy()
        self.file_publish_button.Hide()
        publish(self.upload_target)

app = wx.App()
frame = MainFrame(None, title="Upload Tool")
frame.Show()
app.MainLoop()    
