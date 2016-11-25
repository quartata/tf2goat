# tf2goat

A bidirectional SE <-> Source (not just TF2) chat relay. Requires the latest version of Source.Python and [ChatExchange-Source.Python](https://github.com/quartata/ChatExchange-Source.Python). After installing both, simply move `tf2goat` into `<mod folder>/addons/source-python/plugins/` and edit `config.json`:

    email: The login email of the chat relay's account. (Note that it needs at least 20 rep, and if you want !trash to work it needs to be a room owner).
    password: The login password.
    me: The numerical user ID of the chat relay's account -- this is the number that comes after chat.stackexchange.com/users/... when viewing its profile.
    elevated: An array of user IDs representing people with admin permissions: they can run !rcon, !rm and !trash.
    room_num: The room number that the chat relay should talk in.
    se_color: The color code used for showing SE messages in-game. Use SayText2 colors not SayText.
    censors: An array of arrays of the form [<regex pattern>, <substitution>] -- the chat relay will perform these substitutions on messages going from TF2 to SE.
    announce_se_commands: Display in TF2 when a user runs a command on SE. (1 is True, 0 is False).

Thanks to @printf for help on various things.
