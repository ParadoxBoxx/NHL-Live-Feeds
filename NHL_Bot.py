import discord
import aiohttp
import asyncio
import json
import datetime

BASE_API_URL = "https://statsapi.web.nhl.com"
LIVE_GAME_URL = "https://statsapi.web.nhl.com/api/v1/game/{0}/feed/live"
SCHEDULE_URL = "https://statsapi.web.nhl.com/api/v1/schedule?date=2020-01-02"
TEAM_URL = "https://statsapi.web.nhl.com/api/v1/teams/{0}"
PLAYER_PICTURE_URL = "https://nhl.bamcontent.com/images/headshots/current/168x168/{0}.jpg"
TEAM_COLOR = [
    0Xffffff, # None
    0xcc0b2b, # NJD
    0x085399, # NYI
    0x0639a6, # NYR
    0xf85f25, # PHI
    0xfcb631, # PIT
    0xfbb42d, # BOS
    0x022753, # BUF
    0xbf022b, # MTL
    0xe00231, # OTT
    0x043f7b, # TOR
    0Xffffff, # None 
    0xcc0b2b, # CAR
    0xe3133d, # FLA
    0x073f7e, # TBL
    0xe1002a, # WSH
    0xd30031, # CHI
    0xe0002d, # DET
    0xfeb731, # NSH
    0x075399, # STL
    0xe10026, # CGY
    0x872433, # COL
    0xf36631, # EDM
    0x022e55, # VAN
    0x111111, # ANA
    0x086a4e, # DAL
    0x181415, # LAK
    0Xffffff, # None
    0x0a6c80, # SJS
    0x022653, # CBJ
    0x064932, # MIN
    0Xffffff, # 31
    0Xffffff, # 32
    0Xffffff, # 33
    0Xffffff, # 34
    0Xffffff, # 35
    0Xffffff, # 36
    0Xffffff, # 37
    0Xffffff, # 38
    0Xffffff, # 39
    0Xffffff, # 40
    0Xffffff, # 41
    0Xffffff, # 42
    0Xffffff, # 43
    0Xffffff, # 44
    0Xffffff, # 45
    0Xffffff, # 46
    0Xffffff, # 47
    0Xffffff, # 48
    0Xffffff, # 49
    0Xffffff, # 50
    0Xffffff, # 51
    0x051e40, # WPG
    0x8b2534, # PHX
    0x303e47 # VGK
]

client = discord.Client()
data = {}
# conn = aiohttp.TCPConnector(limit=1)
session = aiohttp.ClientSession()

async def return_url_as_json(url_string):
    global session
    while True:
        async with session.get(url_string) as response:
            if response.status != 200:
                log_time = datetime.datetime.now()
                print(log_time.strftime("[%Y-%m-%d %H:%M:%S] - ") + "Didn't get a 200, sleeping.")
                await asyncio.sleep(10)
            else:
                return json.loads(await response.text())

async def load_data():
    global data
    try:
        with open("bot.data", "r") as f:
            data = json.loads(f.read())
    except FileNotFoundError as e:
        pass

    client.loop.create_task(forever_loop())


def create_embed(play_obj):

    embed = discord.Embed(title=play_obj["result"]["eventTypeId"].replace("_"," ").title())
    embed.description = play_obj["result"]["description"]
    try:
        embed.set_author(name=play_obj["team"]["triCode"])
    except KeyError:
        embed.set_author(name="NHL")
    try:
        embed.color = TEAM_COLOR[play_obj["team"]["id"]]
    except KeyError:
        pass
    try:
        embed.set_thumbnail(url=PLAYER_PICTURE_URL.format(play_obj["players"][0]["player"]["id"]))
    except KeyError:
        pass
    try:
        embed.set_footer(text="NHL and the NHL Shield are registered trademarks of the National Hockey League. NHL and NHL team marks are the property of the NHL and its teams. © NHL 2020. All Rights Reserved.")
        return embed
    except:
        print(log_time.strftime("[%Y-%m-%d %H:%M:%S] - ") + "OOPSIE! " + play_obj["description"])

def recursive_dict_search(search_dict, search_list):
    search_term = search_list.pop(0)
    if search_term in search_dict:
        if len(search_list) == 0:
            return search_dict[search_term]
        else:
            return recursive_dict_search(search_dict[search_term], search_list)
    else:
        return None
    

async def forever_loop():
    global data
    global session
    global client

    while True:
        games_category = None
        while games_category is None:
            games_category = discord.utils.get(client.get_all_channels(), name="Games", guild__name="NHL Live Feeds")
        if not data:
            # No data, get the schedule
            schedule_json = await return_url_as_json(SCHEDULE_URL)
            for old_channel in games_category.channels:
                await old_channel.delete()

        if schedule_json["totalGames"] <= 0:
            log_time = datetime.datetime.now()
            print(log_time.strftime("[%Y-%m-%d %H:%M:%S] - ") +  "No games today.")
        elif schedule_json["totalGames"] > 0:
            for game in schedule_json["dates"][0]["games"]:
                home_json = await return_url_as_json(TEAM_URL.format(str(game["teams"]["home"]["team"]["id"])))
                away_json = await return_url_as_json(TEAM_URL.format(str(game["teams"]["away"]["team"]["id"])))
                new_game_channel = await games_category.create_text_channel(away_json["teams"][0]["abbreviation"] + " at " + home_json["teams"][0]["abbreviation"])
                data[str(game["gamePk"])] = {
                    "gamePk": game["gamePk"],
                    "gameDateTime": datetime.datetime.strptime(game["gameDate"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc),
                    "home": {
                        "id": game["teams"]["home"]["team"]["id"],
                        "name": game["teams"]["home"]["team"]["name"],
                        "abbreviation": home_json["teams"][0]["abbreviation"]
                    },
                    "away": {
                        "id": game["teams"]["away"]["team"]["id"],
                        "name": game["teams"]["away"]["team"]["name"],
                        "abbreviation": away_json["teams"][0]["abbreviation"]
                    },
                    "discord_channel": new_game_channel,
                    "plays": {}
                }

            for gpk in data:
                client.loop.create_task(monitor_game(gpk))

        now = datetime.datetime.now()
        tomorrow = now + datetime.timedelta(days=1)
        tomorrow = tomorrow.replace(hour=12, minute=5, second=0, microsecond=0)
        log_time = datetime.datetime.now()
        print(log_time.strftime("[%Y-%m-%d %H:%M:%S] - ") +  "main loop sleeping " + str((tomorrow - now).total_seconds()) + " seconds.")
        await asyncio.sleep((tomorrow - now).total_seconds())


async def monitor_game(gamePk):
    global data

    now = datetime.datetime.now().astimezone(datetime.timezone.utc)
    if now < data[gamePk]["gameDateTime"]:
        await asyncio.sleep((data[gamePk]["gameDateTime"] - now).total_seconds())
    
    game_complete = False

    while not game_complete:
        log_time = datetime.datetime.now()
        print(log_time.strftime("[%Y-%m-%d %H:%M:%S] - ") +  "Checking for update for {} at {}".format(data[gamePk]["away"]["abbreviation"], data[gamePk]["home"]["abbreviation"]))
        live_json = await return_url_as_json(LIVE_GAME_URL.format(str(gamePk)))

        # See what new plays we have as well as update preexisting plays
        for event in live_json["liveData"]["plays"]["allPlays"]:
            if event["about"]["eventIdx"] not in data[gamePk]["plays"]:
                data[gamePk]["plays"][event["about"]["eventIdx"]] = {
                    "NHLAPI": event,
                    "other": {}
                }
                #data[gamePk]["plays"][event["about"]["eventIdx"]]["NHLAPI"] = event
                data[gamePk]["plays"][event["about"]["eventIdx"]]["other"]["discord_message_obj"] = None
                data[gamePk]["plays"][event["about"]["eventIdx"]]["other"]["posted"] = "new"
            else:
                if data[gamePk]["plays"][event["about"]["eventIdx"]]["NHLAPI"] != event:
                    print("Found an edited event.")
                    data[gamePk]["plays"][event["about"]["eventIdx"]]["NHLAPI"] = event
                    data[gamePk]["plays"][event["about"]["eventIdx"]]["other"]["posted"] = "edited"
                else:
                    print("play already existed, no changes.")

        # Now that our internal data model is updated, we need to update discord as necessary.
        for playIdx in data[gamePk]["plays"]:
            if data[gamePk]["plays"][playIdx]["other"]["posted"] is "new":
                discord_message_obj = await data[gamePk]["discord_channel"].send(embed=create_embed(data[gamePk]["plays"][playIdx]["NHLAPI"]))
                data[gamePk]["plays"][playIdx]["other"]["discord_message_obj"] = discord_message_obj
                data[gamePk]["plays"][playIdx]["other"]["posted"] = "posted"
            elif data[gamePk]["plays"][playIdx]["other"]["posted"] is "edited":
                await discord_message_obj.edit(embed=create_embed(data[gamePk]["plays"][playIdx]["NHLAPI"]))
                data[gamePk]["plays"][playIdx]["other"]["posted"] = "posted"

        if live_json["gameData"]["status"]["codedGameState"] is "7":
            log_time = datetime.datetime.now()
            print(log_time.strftime("[%Y-%m-%d %H:%M:%S] - ") +  "{} at {} is complete, deleting in one hour.".format(data[gamePk]["away"]["abbreviation"], data[gamePk]["home"]["abbreviation"]))
            await asyncio.sleep(3600)
            await data[gamePk]["discord_channel"].delete()
            data.pop(gamePk)
            game_complete = True
        else:
            await asyncio.sleep(1)


@client.event
async def on_ready():
    log_time = datetime.datetime.now()
    print(log_time.strftime("[%Y-%m-%d %H:%M:%S] - ") +  "Discord Ready")
    client.loop.create_task(load_data())

with open("token.data","r") as f:
    client.run(f.read())
