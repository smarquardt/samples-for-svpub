# Samples for Street View Publish API

This repository contains experimental tools and samples for uploading videos
to the Street View Publish API as geo-referenced "photoSequences".

Public documentation for the Street View Publish API is available here:
https://developers.google.com/streetview/publish/

Note that access to the photoSequence methods in the Street View Publish API
is currently (March 2018) by invitation only.

## Video upload tools

There are four upload utilities, each to demonstrate a different scenario:

* basic_uploader : Demonstrates the most basic scenario of uploading a
video where all geo-metadata is embedded inside the video file.

* standalone_uploader : Demonstrates uploading a video that does not
contain embedded geo-metadata, instead using a standalone GPX file
alongside the video.  Timestamps must be precisely synced down to the second
for this to work properly and yield good results.

* gopro_fusion_uploader : Demonstrates how to upload a stitched video from
the GoPro Fusion.  This tool also requires the unstitched video file from
the front-facing camera, because the geo-metadata is not passed through
during stitching and so we need to extract it from the unstitched file.

* gopro_fusion_timelapse_uploader : Demonstrates how to upload a series
of stills from the Timelapse mode in the GoPro Fusion.  In this case
we convert the stills into a single photoSequence so that we can also
enable automatic blurring of faces and license plates, and connect
all frames sequentially and automatically.


## Configuring video upload tools

1. Enable the Street View Publish API in the Google Cloud Platform Console.
(https://support.google.com/cloud/answer/6158841)

1. Set up OAuth 2.0 (https://support.google.com/cloud/answer/6158849)

1. Click the download button to the right of your new OAuth credentials.

1. Place the downloaded JSON file in the same directory as the video upload
samples and rename it to streetviewpublish_config.json. 

1. If additional dependencies are required, it will be documented in the
individual upload utilities.


## Other tools

In addition to the video upload samples, this repository contains lightweight
tools that may help with publishing content under certain conditions.

* exif2gpx : This utility takes a directory of JPEGs and converts the GPS
metadata inside the EXIF tags of each JPEG into a single GPX file.  This GPX
file can then be passed to the video upload sample in this repository, or 
you can just look at it on a map (you can import GPX at mymaps.google.com) to
visualize and validate the GPS data for an interval photo capture.

* gopro_gps_sync : This utility corrects for issues with the GoPro Fusion
Studio stitching software, where GPS data is not currently (March 2018) passed
through correctly to stitched photos.  The tool will take the GPS metadata
from the EXIF of the original unstitched photos and inject it into the
stitched photos. 


Exiftool is required for these tools, you can get it here: 
https://www.sno.phy.queensu.ca/~phil/exiftool/install.html
