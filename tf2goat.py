from chatexchange.client import Client
from chatexchange.events import MessagePosted
from commands.say import SayFilter
from commands.typed import TypedServerCommand
from core import echo_console
from core.command import _core_command
from cvars import cvar
from engines import server
from filters.players import PlayerIter
from html import unescape
from json import load
from listeners import OnClientActive, OnClientDisconnect, OnConVarChanged, OnLevelInit
from listeners.tick import GameThread
from messages import SayText2
from paths import PLUGIN_PATH
from players.helpers import playerinfo_from_index
from re import compile
from steam import SteamID
from subprocess import run
from time import sleep
from events import Event

file = open(PLUGIN_PATH + "/tf2goat/config.json", "r")
config = load(file)
file.close()

email = config["email"]
password = config["password"]
me = config["me"]
elevated = [0] + config["elevated"]
room_num = config["room_num"]
se_color = config["se_color"]
censors = [(compile(censor[0]), censor[1]) for censor in config["censors"]]
announce_se_commands = config["announce_se_commands"]
announce_se_command_output = config["announce_se_command_output"]
ping_on_reply = config["ping_on_reply"]
branch = config["branch"]

room = None
client = None
mod_abuse = 0

# 5-second rolling average used to determine whether we need to put multiple TF messages in one SE
# WIP
#tf_message_avg = 0
#tf_messages = []

def load():
  global client, room
  
  client = Client("stackexchange.com")
  client.login(email, password)
   
  room = client.get_room(room_num)

  def f():
    room.join()
    room.watch(on_se_chat_message)
  
  GameThread(target=f).start()

def unload():
  client._request_queue.queue.clear()
  room.leave()
  client.logout()

def on_se_chat_message(msg, _):
  if isinstance(msg, MessagePosted) and msg.user.id != me:
    content = unescape(msg.content)

    if content.startswith("!"):
      command_dispatch(content.split(" ", 1), msg.user)      
      if announce_se_commands:
        SayText2("\x07" + se_color + "[SE] " + msg.user.name + "\x01: " + content).send()
    else:
      SayText2("\x07" + se_color + "[SE] " + msg.user.name + "\x01: " + content).send()

@SayFilter
def on_tf_chat_message(msg, index, team_only):
  if index and not team_only:
    content = msg.command_string

    for pattern, censor in censors:
      content = pattern.sub(censor, content)
  
    #tf_messages.append(msg.command_string)
    player_info = playerinfo_from_index(index)
    if player_info.is_dead():
      room.send_message("**[TF2] \*DEAD\* " + player_info.name + "**: " + content)
    else:
      room.send_message("**[TF2] " + player_info.name + "**: " + content)

  return True

@TypedServerCommand("goat_cmd")
def console_command(_, command):
  command_dispatch(command.split(" ", 1), None)

def command_dispatch(cmd, sender):
  id = sender.id if sender else 0
  
  if cmd[0] == "!status":
    send_command_response("Name: %s\nMap: %s\nPlayers: %d/%d (%d bots)\nTags: %s" % (
      server.server.name,
      server.server.map_name, 
      server.server.num_clients, server.server.max_clients, server.server.num_fake_clients,
      cvar.find_var("sv_tags").get_string() 
    ), sender, True)
  elif cmd[0] == "!players":
    msg = "\n".join("%s%s - **%s** (http://steamcommunity.com/profiles/%s): %s kills/%s deaths" % (
      "\*DEAD\* " if playerinfo_from_index(p.userid).is_dead(),
      "RED" if p.team == 2 else "BLU" if p.team == 3 else "SPEC",
      p.name, SteamID.parse(p.steamid if p.steamid != "BOT" else "[U:1:22202]").to_uint64(), 
      p.kills, p.deaths
    ) for p in PlayerIter())
    
    send_command_response(msg if msg else "No players.", sender, True)
  elif cmd[0] == "!abuse":
    send_command_response("Admin abuse: " + str(mod_abuse) + "/11", sender, False)
  elif cmd[0] == "!rcon":
    if id in elevated:
      server.queue_command_string(cmd[1])
    else:
      send_command_response("You do not have permission to do that.", sender, False)
  elif cmd[0] == "!rm":
    if id in elevated:
      msg = client.get_message(int(cmd[1]))
      msg.delete()
    else:
      send_command_response("You do not have permission to do that.", sender, False)
  elif cmd[0] == "!trash":
    if id in elevated:
      msg = client.get_message(int(cmd[1]))
      msg.move("19718")
    else:
      send_command_response("You do not have permission to do that.", sender, False)
  elif cmd[0] == "!pull":
    if id in elevated:
      result = run(["git", "-C", PLUGIN_PATH + "/tf2goat/", "pull", "origin", branch])
      
      if result.returncode == 0:
        send_command_response("Pulled; restarting in 5 seconds...", sender, False)
        sleep(5)
        _core_command.reload_plugin("tf2goat")
      else:
        send_command_response("Pull failed. Return code: %d" % result.returncode, sender, False)
    else:
      send_command_response("You do not have permission to do that.", sender, False)
  else:
    send_command_response("No such command.", sender, False)

def send_command_response(message, sender, multiline):
  if sender:
    if ping_on_reply:
      # TODO: Reply to a specific message using ":<message id>"
      if multiline:
        message = message + "\n@" + sender.name
      else:
        message = "@" + sender.name + " " + message
    if announce_se_command_output:
      # Not sure how messy this will be for multi-line output
      SayText2("\x07" + se_color + "[SE] TF2Goat\x01: "+ message).send()
    room.send_message(message)
  else:
    echo_console(message)

#def tf_avg_timer():
#  tf_message_avg = len(tf_messages)/6
#  threading.Timer(30, tf_avg_timer).start()
    
@OnClientActive
def report_connect(index):
  player_info = playerinfo_from_index(index)
  if not player_info.is_fake_client():
    room.send_message(player_info.name + " connected")

@OnClientDisconnect
def report_disconnect(index):
  player_info = playerinfo_from_index(index)
  if not player_info.is_fake_client():
    room.send_message(player_info.name + " disconnected")

@OnLevelInit
def report_changemap(map_name):
  global mod_abuse 

  mod_abuse = 0
  room.send_message("Changing map to " + map_name)

@OnConVarChanged
def on_mod_abuse(cvar, value):
  global mod_abuse

  if cvar.default == value and cvar.flags & 256:
    mod_abuse += 1

@Event("player_changename")
def on_player_change_name(event):
  room.send_message("\* Player %s changed name to %s" % event["oldname"], event["newname"])

