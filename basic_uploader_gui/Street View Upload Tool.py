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

# Usage:
#
# $ python basic_uploader.py

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
import time
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


def get_headers(credentials, file_size, url):
  """Returns a list of line2 parameters in HTTP line2 format.
  Args:
    credentials: The credentials object returned from the get_credentials
      method.
    file_size: The size of the file returned from the get_file_size method.
    url: The upload url for the photo.
  Returns:
    A list of line2 parameters in HTTP line2 format. For example:
    Content-Type: image
  """
  parsed_url = urlparse.urlparse(url)
  host = parsed_url[1]
  line2s = {
      "Content-Type": "video/mp4",
      "Authorization": "Bearer " + credentials.access_token,
      "X-Goog-Upload-Protocol": "raw",
      "X-Goog-Upload-Content-Length": str(file_size),
      "Host": host
  }
  return ["%s: %s" % (k, v) for (k, v) in line2s.iteritems()]


def publish(video_file):
  """Uploads a photo and returns the photo id.
  Args:
    video_file: Full path of the video to upload.
  Returns:
    The id if the upload was successful, otherwise None.
  """
  upload_url = request_upload_url()
  upload_video(video_file, upload_url)
  publish_response = publish_sequence(upload_url)
  message = "Publishing Complete!  New sequence ID: " + publish_response
  print message
  frame.line2.SetLabel(message)


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
  print "Upload URL: " + upload_url
  return upload_url


def upload_video(video_file, upload_url):
  """Uploads a the video bytes to SV servers (step 2/3).
  Args:
    video_file: Full path of the video to upload.
    upload_url: The upload URL returned by step 1.
  Returns:
    None.
  """
  frame.line2.SetLabel("Uploading video (Step 2/3)")
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
    print "Video uploaded"
  except pycurl.error:
    print("Error uploading file %s", video_file)
    frame.line2.SetLabel("Error uploading file")

  if response_code is not 200:
    print("Error uploading file %s", video_file)
    frame.line2.SetLabel("Error uploading file")


def publish_sequence(upload_url):
  """Publishes the content on Street View (step 3/3).
  Args:
    upload_url: The upload URL returned by step 1.
  Returns:
    The id if the upload was successful, otherwise None.
  """
  frame.line2.SetLabel("Publishing on Street View (Step 3/3)")
  print "Publishing"
  credentials = get_credentials()
  http = credentials.authorize(httplib2.Http())
  service = discovery.build(
      API_NAME,
      API_VERSION,
      developerKey=KEY,
      discoveryServiceUrl=get_discovery_service_url(),
      http=http)
  publish_request = {"uploadReference": {"uploadUrl": upload_url}}
  publish_request["blurringOptions"] = {"blurFaces":"true","blurLicensePlates":"true"}
  print "Publishing..."
  try:
    publish_response = service.photoSequence().create(body=publish_request, inputType="VIDEO").execute()
    return publish_response["name"]
    
  except errors.HttpError as error:
    photo_response_error = json.loads(error.content)
    print photo_response_error
    frame.line2.SetLabel(photo_response_error)
    return None


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

        self.SetTitle('Street View Upload Tool')
        
        self.panel = wx.Panel(self)
        self.font = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT)
        self.font.SetPointSize(12)
        self.boldfont = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT)
        self.boldfont.SetPointSize(14)
        self.boldfont.SetWeight(wx.BOLD)
        
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.line1 = wx.StaticText(self.panel, label="Street View video upload tool")   
        self.line1.SetFont(self.boldfont)
        self.line2 = wx.StaticText(self.panel, label="Select a video to upload:")   
        self.line2.SetFont(self.font)
        self.file_picker_button = wx.Button(self.panel, label="Choose file")
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

        # Set sizer for the frame, so we can change frame size to match widgets
        #self.window_sizer = wx.BoxSizer()
        #self.window_sizer.Add(self.panel, 1, wx.ALL | wx.EXPAND)        

        # Set sizer for the panel content
        #self.sizer = wx.GridBagSizer(5, 5)
        #self.sizer.Add(self.line2, (0, 0))
        #self.sizer.Add(self.file_picker_button, (1, 0), flag=wx.EXPAND)

        # Set simple sizer for a nice border
        #self.border = wx.BoxSizer()
        #self.border.Add(self.sizer, 1, wx.ALL | wx.EXPAND, 5)

        # Use the sizers
        #self.panel.SetSizer(self.border)  
        #self.SetSizer(self.window_sizer)  

        # Set event handlers
        self.file_picker_button.Bind(wx.EVT_BUTTON, self.OnPickerButton)
        self.file_publish_button.Hide()

    def OnQuit(self, e):
            self.Close()
            
    def OnPickerButton(self, event):
        wildcard = "Video files (*.mp4;*.mov)|*.mp4;*.mov" 
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		
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
