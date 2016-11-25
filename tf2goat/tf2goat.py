from chatexchange6.client import Client
from chatexchange6.events import MessagePosted
from commands.say import SayFilter
from cvars import cvar
from engines import server
from filters.players import PlayerIter
from html import unescape
from json import load
from listeners import OnClientActive, OnClientDisconnect, OnConVarChanged, OnLevelInit
from listeners.tick import GameThread
from messages import SayText2
from players.helpers import playerinfo_from_index
from re import compile

config = load(open("config.json", "r"))

email = config["email"]
password = config["password"]
me = config["me"]
elevated = config["elevated"]
room_num = config["room_num"]
se_color = config["se_color"]
censors = [(re.compile(censor[0]), censor[1]) for censor in config["censors"]]
announce_se_commands = config["announce_se_commands"]

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
      command_dispatch(content.split(" ", 1), msg.user.id, client)      
      if announce_se_commands:
        SayText2("\x07"+ se_color +"[SE] "+ msg.user.name + "\x01: " + content).send()
    else:
      SayText2("\x07"+ se_color +"[SE] "+ msg.user.name + "\x01: " + content).send()

@SayFilter
def on_tf_chat_message(msg, index, team_only):
  content = msg.command_string

  for pattern, censor in censors:
    content = pattern.sub(censor, content)
  
  #tf_messages.append(msg.command_string)
  player_info = playerinfo_from_index(index)
  if index and not team_only:
    if player_info.is_dead():
      room.send_message("**[TF2] \*DEAD\* " + player_info.name + "**: " + content)
    else:
      room.send_message("**[TF2] " + player_info.name + "**: " + content)

  return True

def command_dispatch(cmd, id, client):
  if cmd[0] == "!status":
    room.send_message("Name: %s\n Map: %s\n Players: %d/%d (%d bots)\n Tags: %s" % (
      server.server.name,
      server.server.map_name, 
      server.server.num_clients, server.server.max_clients, server.server.num_fake_clients,
      cvar.find_var("sv_tags").get_string() 
    ))
  elif cmd[0] == "!players":
    msg = "\n".join("%s: %s" % (p.name, p.kills) for p in PlayerIter())
    room.send_message(msg if msg else "No players.")
  elif cmd[0] == "!abuse":
    room.send_message("mod abuse: " + str(mod_abuse) + "/11")
  elif cmd[0] == "!rcon":
    if id in elevated:
      server.queue_command_string(cmd[1])
    else:
      room.send_message("You do not have permission to do that.")
  elif cmd[0] == "!rm":
    if id in elevated:
      msg = client.get_message(int(cmd[1]))
      msg.delete()
    else:
      room.send_message("You do not have permission to do that.")
  elif cmd[0] == "!trash":
    if id in elevated:
      msg = client.get_message(int(cmd[1]))
      msg.move("19718")
    else:
      room.send_message("You do not have permission to do that.")
  else:
    room.send_message("No such command.")

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

