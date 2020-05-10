VttThumbZilla
============
Python scripts to generate tooltip thumbnail images for videos (e.g. mp4, m4v, avi) & associated WebVTT files.

Reference idea author [vlanard](https://github.com/vlanard)

Components
============

Written on Python 3

makesprites.py
--------------
Python script to generate thumbnail images for a video, put them into an grid-style sprite,
and create a Web VTT file that maps the sprite images to the video segments.

Required dependencies (expected in PATH):
* ffmpeg [download here](http://www.ffmpeg.org/download.html)

    Linux<pre>sudo apt update</pre>
    <pre>sudo apt install ffmpeg</pre>
* imagemagick [download here](http://www.imagemagick.org/script/index.php) or [here](http://www.imagemagick.org/script/index.php) or on Mac, use Macports: <pre>sudo port install ImageMagick</pre>
    Linux <pre>sudo apt install imagemagick-6.q16</pre>

Sample Usage:

    python3 makesprites.py /path/to/myvideofile.mp4

You may want to customize the the following variables in makesprites.py:

    USE_SIPS = False         # True if using MacOSX (creates slightly smaller sprites), else set to False to use ImageMagick resizing
    THUMB_RATE_SECONDS=5   # every Nth second take a snapshot of the video (tested with 30,45,60)
    THUMB_WIDTH=100         # 100-150 is recommended width, smaller size = smaller sprite for user to download

    
And a sample of a generated WebVTT file.

<pre>
WEBVTT

Img 1
00:00:22.000 --> 00:01:07.000
myvideofile_sprite.jpg#xywh=0,0,100,56

Img 2
00:01:07.000 --> 00:01:52.000
myvideofile_sprite.jpg#xywh=100,0,100,56

Img 3
00:01:52.000 --> 00:02:37.000
myvideofile_sprite.jpg#xywh=200,0,100,56

Img 4
00:02:37.000 --> 00:03:22.000
myvideofile_sprite.jpg#xywh=300,0,100,56

Img 5
00:03:22.000 --> 00:04:07.000
myvideofile_sprite.jpg#xywh=400,0,100,56

Img 6
00:04:07.000 --> 00:04:52.000
myvideofile_sprite.jpg#xywh=500,0,100,56
</pre>
