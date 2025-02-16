import queue
import subprocess
import json
import musicbrainzngs as m
import libdiscid
from time import sleep
from enum import Enum
from classes.MediaPlayerInfo import MediaPlayerInfo, CurrentTrackInfo, TrackInfo

class MediaPlayer:
  """
  Contains logic for controlling mpd and getting information about CD.
  """
  class DiskType(Enum):
    AUDIO_CD = 'audio_cd'
    MP3_CD = 'mp3_cd'

  class BranchType(Enum):
    FOLDERS = 'folders'
    ARTISTS = 'artists'
    ALBUMS = 'albums'

  def __init__(self, config):
    self._config = config
    self.MPC_COMMAND = ['mpc']
    self._cd = CD()
    self._mpc = None
    self._current_disk_type = None
    self._media_library = None
    self._current_track_list = None
    self._current_media_library_branch_type_index = None
    self._info_events = None
    self._current_track = 0
    self._volume = 95

  def get_current_info(self, status=True, cur_track_info=True, volume=True, track_list=False, library=False):
    info = MediaPlayerInfo()
    if self.is_running:
      if status:
        status_res = self._run_command('get_property', 'pause')
        info.status = 'paused' if status_res else 'playing'
      if cur_track_info:
        info.cur_track_info = CurrentTrackInfo()
        if self._current_disk_type == MediaPlayer.DiskType.AUDIO_CD:
          chapter_res = self._run_command('get_property', 'chapter')
          self._current_track = chapter_res
          info.cur_track_info.track_number = chapter_res
        elif self._current_disk_type == MediaPlayer.DiskType.MP3_CD:
          playlist_pos_res = self._run_command('get_property', 'playlist-pos')
          self._current_track = playlist_pos_res
          info.cur_track_info.track_number = playlist_pos_res
        if self._current_track is not None:
          time_res = self._run_command('get_property', 'time-pos')
          if time_res is not None:
            time_millis = time_res * 1000
            if self._current_disk_type == MediaPlayer.DiskType.AUDIO_CD:
              for track in self._current_track_list[0:self._current_track]:
                time_millis -= track.total_time
            info.cur_track_info.cur_time = time_millis
      if volume:
        vol = self._run_command('get_property', 'volume')
        if vol is not None:
          self._volume = vol
          info.volume = vol
      if track_list and self._current_track_list is not None:
        info.track_list = list(map(lambda x: x.as_dict(), self._current_track_list))
      if library and self._media_library is not None:
        info.library = self._media_library
    else:
      info.volume = self._volume
      info.status = 'waitingForCD'

    return info

  def poll_info(self):
    try:
      info_event = self._info_events.get_nowait()
      return info_event
    except queue.Empty:
      return None

  def try_play_cd(self):
    """
    Tries to play CD in CD drive, if there is any (or USB drive)
    Sets the current media library branch type and index attribute and puts infor into the info queue
    :return: None
    """
    self._info_events = queue.Queue()
    if not self.is_running:
      cd_type = self._check_for_cd()
      if cd_type is None:
        return
      if cd_type is MediaPlayer.DiskType.AUDIO_CD:
        print('playing audio CD')
        # Todo: Play the CD here
      elif cd_type == MediaPlayer.DiskType.MP3_CD:
        print('playing MP3 CD')
        # Todo: Play the MP3 CD here
        print('MP3 CD not yet supported')
        self._current_media_library_branch_type_index = (MediaPlayer.BranchType.FOLDERS, 0)
      info = self.get_current_info(True, True, True, True, True)
      # fill cur_track_info with zeros, because it may not be initialised yet (loading)
      info.cur_track_info = CurrentTrackInfo()
      info.cur_track_info.cur_time = 0
      info.cur_track_info.track_number = 0
      self._info_events.put(info)

  def _check_for_cd(self):
    self._current_disk_type = None
    self._current_track_list = []
    self._cd.load_cd_info()
    df = []
    if CD.is_cd_inserted():
      if self._cd.numtracks > 1:
        # CD that isn't audio CD has 1 track
        self._current_disk_type = MediaPlayer.DiskType.AUDIO_CD
        try:
          artist = self._cd._cd_info['disc']['release-list'][0]['artist-credit-phrase']
          album = self._cd._cd_info['disc']['release-list'][0]['title']
          self._current_track_list = list(map(
            lambda x, y: TrackInfo(y, artist, album, x['recording']['title']),
            self._cd._cd_info['disc']['release-list'][0]['medium-list'][0]['track-list'],
            self._cd._track_lengths))
        except:
          self._current_track_list = list(map(lambda x: TrackInfo(x), self._cd.track_lengths))
      else:
        print('Not an audio CD')
    print('No CD Found')
    return self._current_disk_type

  @property
  def is_running(self):
    # Todo: Check is running
    return False

  @property
  def currnet_track_list(self):
    return self._current_track_list







class CD:
  """
  Represents CD drive and disc inside.
  """

  def __init__(self):
    self._numtracks = 0
    self._track_lengths = []
    self._cd_info = None

  def load_cd_info(self):
    track_offsets = []
    m.set_useragent('rasp-cd', '0.1', 'https://github.com/mikeygcooper/rasp-cd')
    try:
      this_disc = libdiscid.read('/dev/cdrom')
    except:
      print('DiskID could not read /dev/cdrom')
      self._numtracks = 0
      self._track_lengths = []
      self._cd_info = None
      return
    try:
      self._cd_info = m.get_releases_by_discid(this_disc.id, includes=['recordings', 'artists'], cdstubs=False)
    except m.ResponseError:
      print('Disk not found or database unavailable')
      discid = subprocess.getstatusoutput('cd-discid --musicbrainz')
      if discid[0] == 0:
        output_split = discid[1].split()
        self._numtracks = int(output_split[0])
        track_offsets = list(map(lambda i: int(i), output_split[1:]))
    if self._cd_info is not None:
      if self._cd_info.get('disc'):
        self._numtracks = self._cd_info['disc']['offset-count']
        track_offsets = self._cd_info['disc']['offset-list']
        track_offsets.append(int(self._cd_info['disc']['sectors']))
      elif self._cd_info.get('cdstub'):
        pass
      else:
        print('Unknown disk type from MB - use track numbers')
        discid = subprocess.getstatusputput('cd-discid --musicbrainz')
        if discid[0] == 0:
          output_split = discid[1].split()
          self._numtracks = int(output_split[0])
          track_offsets = list(map(lambda i: int(i), output_split[1:]))
    try:
      self._track_lengths = list(
        map(lambda i, offsets=track_offsets: int((offsets[i + 1] - offsets[i]) * 1000 / 75), range(0, self._numtracks)))
    except:
      self._numtracks = 0
      self._track_lengths = []

  @staticmethod
  def is_cd_inserted():
    try:
      subprocess.check_output(['cd-discid', '--musicbrainz'])
    except subprocess.CalledProcessError:
      return False
    return True

  @property
  def numtracks(self):
    return self._numtracks

  @property
  def track_lengths(self):
    return self._track_lengths
