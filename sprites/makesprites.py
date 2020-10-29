import subprocess
import shlex
import sys
import logging
import os
import datetime
import math
import glob
import pipes
from dateutil import relativedelta

###################################################
"""
 Generate tooltip thumbnail images & corresponding WebVTT file for a video (e.g MP4).
 Final product is one *_sprite.jpg file and one *_thumbs.vtt file.

 DEPENDENCIES: required: ffmpeg & imagemagick
               optional: sips (comes with MacOSX) - yields slightly smaller sprites
    download ImageMagick: http://www.imagemagick.org/script/index.php OR
    http://www.imagemagick.org/script/binary-releases.php (on MacOSX: "sudo port install ImageMagick")
    download ffmpeg: http://www.ffmpeg.org/download.html

 TESTING NOTES: Tested putting time gaps between thumbnail segments, but had no visual effect in JWplayer, so omitted.
                Tested using an offset so that thumbnail would show what would display mid-way through clip rather than
                for the 1st second of the clip, but was not an improvement.
"""
###################################################

"""True to use sips if using MacOSX (creates slightly smaller sprites), else set to False to use ImageMagick"""
USE_SIPS = False

"""Every Nth second take a snapshot"""
THUMB_RATE_SECONDS = 10

"""100-150 is recommended width; I like smaller files"""
THUMB_WIDTH = 200

"""True to skip a thumbnail of second 1; often not a useful image, plus user knows beginning without needing preview"""
SKIP_FIRST = False

"""jpg is much smaller than png, so using jpg"""
SPRITE_NAME = "sprite.jpg"

VTT_FILE_NAME = "thumbs.vtt"
THUMB_OUT_DIR = "thumbs"

"""True to make a unique timestamped output dir each time, else False to overwrite/replace existing outdir"""
USE_UNIQUE_OUT_DIR = False

"""
    set to 1 to not adjust time (gets multiplied by thumbRate);
    On my machine,ffmpeg snapshots show earlier images than expected timestamp by about 1/2 the thumbRate
    (for one vid, 10s thumbrate->images were 6s earlier than expected;45->22s early,90->44 sec early)
"""
TIME_SYNC_ADJUST = -.5

logger = logging.getLogger(sys.argv[0])
logSetup = False


class SpriteTask:
    """small wrapper class as convenience accessor for external scripts"""

    def __init__(self, video_elem):
        self.remote_file = video_elem.startswith("http")
        if not self.remote_file and not os.path.exists(video_elem):
            sys.exit("File does not exist: %s" % video_elem)
        base_file = os.path.basename(video_elem)

        """strip trailing speed suffix from file/dir names, if present"""
        base_file_no_speed = remove_speed(base_file)
        new_out_dir = make_out_dir(base_file_no_speed)
        file_prefix, ext = os.path.splitext(base_file_no_speed)
        sprite_file = os.path.join(new_out_dir, "%s_%s" % (file_prefix, SPRITE_NAME))
        vtt_file = os.path.join(new_out_dir, "%s_%s" % (file_prefix, VTT_FILE_NAME))
        self.video_file = video_elem
        self.vtt_file = vtt_file
        self.sprite_file = sprite_file
        self.out_dir = new_out_dir

    def get_video_file(self):
        return self.video_file

    def get_out_dir(self):
        return self.out_dir

    def get_sprite_file(self):
        return self.sprite_file

    def get_vtt_file(self):
        return self.vtt_file


def make_out_dir(video_elem):
    """create unique output dir based on video file name and current timestamp"""
    base, ext = os.path.splitext(video_elem)
    script = sys.argv[0]
    """make output dir always relative to this script regardless of shell directory"""
    base_path = os.path.dirname(
        os.path.abspath(script))
    if len(THUMB_OUT_DIR) > 0 and THUMB_OUT_DIR[0] == '/':
        output_dir = THUMB_OUT_DIR
    else:
        output_dir = os.path.join(base_path, THUMB_OUT_DIR)
    if USE_UNIQUE_OUT_DIR:
        new_out_dir = "%s.%s" % (os.path.join(output_dir, base), datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    else:
        new_out_dir = "%s_%s" % (os.path.join(output_dir, base), "vtt")
    if not os.path.exists(new_out_dir):
        logger.info("Making dir: %s" % new_out_dir)
        os.makedirs(new_out_dir)
    elif os.path.exists(new_out_dir) and not USE_UNIQUE_OUT_DIR:
        """remove previous contents if reusing out_dir"""
        files = os.listdir(new_out_dir)
        print("Removing previous contents of output directory: %s" % new_out_dir)
        for f in files:
            os.unlink(os.path.join(new_out_dir, f))
    return new_out_dir


def do_cmd(cmd, def_logger=logger):
    """execute a shell command and return/print its output"""
    def_logger.info("START [%s] : %s " % (datetime.datetime.now(), cmd))
    """tokenize args"""
    args = shlex.split(cmd)
    output = None
    try:
        """pipe stderr into stdout"""
        output = subprocess.check_output(args, stderr=subprocess.STDOUT)
    except Exception as e:
        ret = "ERROR   [%s] An exception occurred\n%s\n%s" % (datetime.datetime.now(), output, str(e))
        def_logger.error(ret)
        raise e
    ret = "END   [%s]\n%s" % (datetime.datetime.now(), output)
    def_logger.info(ret)
    sys.stdout.flush()
    return output


def take_snaps(video_elem, new_out_dir, thumb_rate=None):
    """
    take snapshot image of video every Nth second and output to sequence file names and custom directory
        reference: https://trac.ffmpeg.org/wiki/Create%20a%20thumbnail%20image%20every%20X%20seconds%20of%20the%20video
    """
    if not thumb_rate:
        thumb_rate = THUMB_RATE_SECONDS
    """1/60=1 per minute, 1/120=1 every 2 minutes"""
    rate = "1/%d" % thumb_rate
    cmd = "ffmpeg -i %s -f image2 -bt 20M -vf fps=%s -aspect 16:9 %s/tv%%03d.jpg" % (
        pipes.quote(video_elem), rate, pipes.quote(new_out_dir))
    do_cmd(cmd)
    if SKIP_FIRST:
        """remove the first image"""
        logger.info("Removing first image, unneeded")
        os.unlink("%s/tv001.jpg" % new_out_dir)
    count = len(os.listdir(new_out_dir))
    logger.info("%d thumbs written in %s" % (count, new_out_dir))
    """return the list of generated files"""
    return count, get_thumb_images(new_out_dir)


def get_thumb_images(new_dir):
    return glob.glob("%s/tv*.jpg" % new_dir)


def resize(files):
    """
        change image output size to 100 width (originally matches size of video)
        - pass a list of files as string rather than use '*' with sips command because
        subprocess does not treat * as wildcard like shell does
    """
    if USE_SIPS:
        """HERE IS MAC SPECIFIC PROGRAM THAT YIELDS SLIGHTLY SMALLER JPGs"""
        do_cmd("sips --resampleWidth %d %s" % (THUMB_WIDTH, " ".join(map(pipes.quote, files))))
    else:
        """THIS COMMAND WORKS FINE TOO AND COMES WITH IMAGEMAGICK, IF NOT USING A MAC"""
        do_cmd("mogrify -geometry %dx %s" % (THUMB_WIDTH, " ".join(map(pipes.quote, files))))


def get_geometry(file):
    """execute command to give geometry HxW+X+Y of each file matching command
       identify -format "%g - %f\n" *         #all files
       identify -format "%g - %f\n" onefile.jpg  #one file
     SAMPLE OUTPUT
        100x66+0+0 - _tv001.jpg
        100x2772+0+0 - sprite2.jpg
        4200x66+0+0 - sprite2h.jpg"""
    geom = do_cmd("""identify -format "%%g - %%f\n" %s""" % pipes.quote(file))
    parts = geom.decode().split("-", 1)
    """return just the geometry prefix of the line, sans extra whitespace"""
    return parts[0].strip()


def make_vtt(sprite_file, num_segments, coordinates, grid_size, writefile, thumb_rate=None):
    """
        generate & write vtt file mapping video time to each image's coordinates
        in our sprite_map

        split geometry string into individual parts
    """

    """4200x66+0+0 === WxH+X+Y"""
    if not thumb_rate:
        thumb_rate = THUMB_RATE_SECONDS
    wh, xy = coordinates.split("+", 1)
    w, h = wh.split("x")
    w = int(w)
    h = int(h)
    # x,y = xy.split("+")
    # ======= SAMPLE WEBVTT FILE=====
    # WEBVTT
    #
    # 00:00.000 --> 00:05.000
    # /assets/thumbnails.jpg#xywh=0,0,160,90
    #
    # 00:05.000 --> 00:10.000
    # /assets/preview2.jpg#xywh=160,0,320,90
    #
    # 00:10.000 --> 00:15.000
    # /assets/preview3.jpg#xywh=0,90,160,180
    #
    # 00:15.000 --> 00:20.000
    # /assets/preview4.jpg#xywh=160,90,320,180
    # ==== END SAMPLE ========
    base_file = os.path.basename(sprite_file)
    """line buffer for file contents"""
    vtt = ["WEBVTT", ""]
    if SKIP_FIRST:
        """offset time to skip the first image"""
        clip_start = thumb_rate
    else:
        clip_start = 0
    """NOTE - putting a time gap between thumbnail end & next start has no visual effect in JWPlayer, 
    so not doing it."""
    clip_end = clip_start + thumb_rate
    adjust = thumb_rate * TIME_SYNC_ADJUST
    for img_num in range(1, num_segments + 1):
        xywh = get_grid_coordinates(img_num, grid_size, w, h)
        start = get_time_str(clip_start, adjust=adjust)
        end = get_time_str(clip_end, adjust=adjust)
        clip_start = clip_end
        clip_end += thumb_rate
        vtt.append("Img %d" % img_num)
        vtt.append("%s --> %s" % (start, end))  # 00:00.000 --> 00:05.000
        vtt.append("%s#xywh=%s" % (base_file, xywh))
        vtt.append("")  # Linebreak
    vtt = "\n".join(vtt)
    """output to file"""
    write_vtt(writefile, vtt)


def get_time_str(numseconds, adjust=None):
    """ convert time in seconds to VTT format time (HH:)MM:SS.ddd """

    """ offset the time by the adjust amount, if applicable """
    if adjust:
        """ don't go below 0! can't have a negative timestamp """
        seconds = max(numseconds + adjust, 0)
    else:
        seconds = numseconds
    delta = relativedelta.relativedelta(seconds=seconds)
    return "%02d:%02d:%02d.000" % (delta.hours, delta.minutes, delta.seconds)


# def get_grid_coordinates(imgnum, gridsize, w, h):
#     """ given an image number in our sprite, map the coordinates to it in X,Y,W,H format"""
#     y = (imgnum - 1) / gridsize
#     x = (imgnum - 1) - (y * gridsize)
#     imgx = x * w
#     imgy = y * h
#     return "%s,%s,%s,%s" % (imgx, imgy, w, h)

def get_grid_coordinates(img_num, grid_size, w, h):
    """ given an image number in our sprite, map the coordinates to it in X,Y,W,H format"""
    y = int((img_num - 1) / grid_size)
    x = int((img_num - 1) - (y * grid_size))
    img_x = x * w
    img_y = y * h
    return "%s,%s,%s,%s" % (img_x, img_y, w, h)


def make_sprite(out_dir, sprite_file, coordinates, grid_size):
    """
        montage _tv*.jpg -tile 8x8 -geometry 100x66+0+0 montage.jpg  #GRID of images
           NOT USING: convert tv*.jpg -append sprite.jpg     #SINGLE VERTICAL LINE of images
           NOT USING: convert tv*.jpg +append sprite.jpg     #SINGLE HORIZONTAL LINE of images
        base the sprite size on the number of thumbs we need to make into a grid.
    """
    grid = "%dx%d" % (grid_size, grid_size)

    # print('gridsize:', grid_size)
    # print('outdir:', out_dir)
    # print('coords:', coordinates)
    # print('spritefile:', sprite_file)

    """if video had more than 144 thumbs, would need to be bigger grid, making it big to cover all our case"""
    cmd = "montage %s/tv*.jpg -tile %s -geometry %s %s" % (pipes.quote(out_dir), grid, coordinates, pipes.quote(
        sprite_file))
    do_cmd(cmd)


def write_vtt(vtt_file, contents):
    """ output VTT file """
    with open(vtt_file, mode="w") as h:
        h.write(contents)
    logger.info("Wrote: %s" % vtt_file)


def remove_speed(video_elem):
    """some of my files are suffixed with datarate, e.g. myfile_3200.mp4;
     this trims the speed from the name since it's irrelevant to my sprite names (which apply regardless of speed);
     you won't need this if it's not relevant to your filenames"""
    video_elem = video_elem.strip()
    speed = video_elem.rfind("_")
    speed_last = video_elem.rfind(".")
    may_be_speed = video_elem[speed + 1:speed_last]
    try:
        int(may_be_speed)
        video_elem = video_elem[:speed] + video_elem[speed_last:]
    except Exception:
        pass
    return video_elem


def run(activity, thumb_rate=None):
    add_logging()
    if not thumb_rate:
        thumb_rate = THUMB_RATE_SECONDS
    out_dir = activity.get_out_dir()
    sprite_file = activity.get_sprite_file()

    """create snapshots"""
    num_files, thumb_files = take_snaps(activity.get_video_file(), out_dir, thumb_rate=thumb_rate)

    """resize them to be mini"""
    resize(thumb_files)

    """get coordinates from a resized file to use in sprite mapping"""
    grid_size = int(math.ceil(math.sqrt(num_files)))

    """use the first file (since they are all same size) to get geometry settings"""
    coordinates = get_geometry(thumb_files[0])

    """convert small files into a single sprite grid"""
    make_sprite(out_dir, sprite_file, coordinates, grid_size)

    """generate a vtt with coordinates to each image in sprite"""
    make_vtt(sprite_file, num_files, coordinates, grid_size, activity.get_vtt_file(), thumb_rate=thumb_rate)


def add_logging():
    global logSetup
    if not logSetup:
        base_script = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        """new log per job so we can run this program concurrently"""
        log_filename = 'logs/%s.%s.log' % (base_script, datetime.datetime.now().strftime(
            "%Y%m%d_%H%M%S"))
        """CONSOLE AND FILE LOGGING"""
        print("Writing log to: %s" % log_filename)
        if not os.path.exists('logs'):
            os.makedirs('logs')
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(log_filename)
        logger.addHandler(handler)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        logger.addHandler(ch)
        """set flag so we don't reset log in same batch"""
        logSetup = True


if __name__ == "__main__":
    if not len(sys.argv) > 1:
        sys.exit("Please pass the full path or url to the video file for which to create thumbnails.")
    if len(sys.argv) == 3:
        THUMB_OUT_DIR = sys.argv[2]
    video_file = sys.argv[1]
    task = SpriteTask(video_file)
    run(task)
