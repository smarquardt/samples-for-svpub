This tool will allow you to upload a folder of 360-degree images to Street View and have them be auto-connected and blurred.  The images must have GPS data saved in their EXIF.  The tool is currently designed to parse the file structure output by the GoPro Fusion, and iterates through the files sequentially by filename.  A future improvement would be to handle an entire folder in the order of EXIF capture time, which would also remove the dependency on GoPro-style file names.

Before you can use the tool, you must add your streetviewpublish_config.json file in the same folder, replace the placeholder value for KEY at the beginning of the script, and then build the app by running:
python setup.py py2app --emulate-shell-environment

In addition to the dependencies described in the root README, you will also need ffmpeg-python, pyexiftool, wxpython, and py2app.
