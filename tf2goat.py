from chatexchange.client import Client
from chatexchange.events import MessagePosted
from commands.say import SayFilter
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

file = open(PLUGIN_PATH + "/tf2goat/config.json", "r")
config = load(file)
file.close()

email = config["email"]
password = config["password"]
me = config["me"]
elevated = config["elevated"]
room_num = config["room_num"]
se_color = config["se_color"]
censors = [(compile(censor[0]), censor[1]) for censor in config["censors"]]
announce_se_commands = config["announce_se_commands"]
announce_se_command_output = config["announce_se_command_output"]
ping_on_reply = config["ping_on_reply"]

room = None
mod_abuse = 0

# 5-second rolling average used to determine whether we need to put multiple TF messages in one SE
# WIP
#tf_message_avg = 0
#tf_messages = []

def load():
  global room
  
  client = Client("stackexchange.com")
  client.login(email, password)
   
  room = client.get_room(room_num)

  def f():
    room.join()
    room.watch(on_se_chat_message)
  
  GameThread(target=f).start()

def unload():
  room.leave()

def on_se_chat_message(msg, client):
  if isinstance(msg, MessagePosted) and msg.user.id != me:
    content = unescape(msg.content)

    if content.startswith("!"):
      command_dispatch(content.split(" ", 1), msg.user, client)      
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

def command_dispatch(cmd, sender, client):
  id = sender.id
  if cmd[0] == "!status":
    send_command_response("Name: %s\n Map: %s\n Players: %d/%d (%d bots)\n Tags: %s" % (
      server.server.name,
      server.server.map_name, 
      server.server.num_clients, server.server.max_clients, server.server.num_fake_clients,
      cvar.find_var("sv_tags").get_string() 
    ), sender)
  elif cmd[0] == "!players":
    msg = "\n".join("%s - [%s](http://steamcommunity.com/profiles/%s): %s kills/%s deaths" % (
      "RED" if p.team == 2 else "BLU" if p.team == 3 else "SPEC",
      p.name, SteamID.parse(p.steamid).to_uint64(), 
      p.kills, p.deaths
    ) for p in PlayerIter())
    
    send_command_response(msg if msg else "No players.", sender)
  elif cmd[0] == "!abuse":
    send_command_response("mod abuse: " + str(mod_abuse) + "/11", sender)
  elif cmd[0] == "!rcon":
    if id in elevated:
      server.queue_command_string(cmd[1])
    else:
      send_command_response("You do not have permission to do that.", sender)
  elif cmd[0] == "!rm":
    if id in elevated:
      msg = client.get_message(int(cmd[1]))
      msg.delete()
    else:
      send_command_response("You do not have permission to do that.", sender)
  elif cmd[0] == "!trash":
    if id in elevated:
      msg = client.get_message(int(cmd[1]))
      msg.move("19718")
    else:
      send_command_response("You do not have permission to do that.", sender)
  else:
    send_command_response("No such command.", sender)

def send_command_response(message, sender):
  if ping_on_reply:
    # TODO: Reply to a specific message using ":<message id>"
    message = "@" + sender.name + " " + message
  if announce_se_command_output:
    # Not sure how messy this will be for multi-line output
    SayText2("\x07" + se_color + "[SE] TF2Goat\x01: "+ message).send()
  room.send_message(message)
  
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

