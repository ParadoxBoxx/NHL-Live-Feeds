import discord
import aiohttp
import asyncio
import json
import datetime

LIVE_GAME_URL = "https://statsapi.web.nhl.com/api/v1/game/{0}/feed/live"
SCHEDULE_URL = "https://statsapi.web.nhl.com/api/v1/schedule"
TEAM_URL = "https://statsapi.web.nhl.com/api/v1/teams/{0}"

client = discord.Client()
data = {}


async def no_data():

    # Loop forever
    while True:

        # Delete all irelevant game data
        games_category = discord.utils.get(client.get_all_channels(), name="Games", guild__name="NHL Live Feeds")
        for old_channel in games_category.channels:
            await old_channel.delete()

        # Set up a session to get the schedule
        conn = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(connector=conn) as session:
            # Get today's schedule
            schedule_json = await return_url_as_json(session, SCHEDULE_URL)
        
            # Check to make sure there are games today
            if len(schedule_json["dates"]) > 0:
                
                # for every game on the schedule today
                for game in schedule_json["dates"][0]["games"]:
                    
                    # Create the discord channel
                    home_json = await return_url_as_json(session, TEAM_URL.format(str(game["teams"]["home"]["team"]["id"])))
                    home = home_json["teams"][0]
                    away_json = await return_url_as_json(session, TEAM_URL.format(str(game["teams"]["away"]["team"]["id"])))
                    away = away_json["teams"][0]
                    new_game_channel = await games_category.create_text_channel(away["abbreviation"] + " at " + home["abbreviation"])

                    # Create the game object
                    # Check to make sure the game doesn't already exist
                    if str(game["gamePk"]) not in data:
                        data[str(game["gamePk"])] = {
                            "NHL_API_ID": game["gamePk"],
                            "discord_channel_obj": new_game_channel,
                            "home": home,
                            "away": away,
                            "plays": {},
                            "complete": False,
                            "datetime_to_delete": datetime.datetime(1970,1,1,0,0,0)
                        }
                    else:
                        # The game already existed, spit out an error
                        print("DUPLICATE GAME!!!")

                    # Start monitoring for that game
                    client.loop.create_task(monitor(str(game["gamePk"])))

        # Wait until tomorrow, and start process over again
        today = datetime.datetime.now()
        wait_time = datetime.datetime(today.year,today.month, today.day + 1, 12,5,00)
        await asyncio.sleep((wait_time - datetime.datetime.now()).total_seconds())


async def monitor(gamePk):
    
    # This needs to coninually happen, we will break out of the loop when the game is over
    while True:

        #print("Checking " + gamePk)
        # Get the plays that have happened
        # Set up a session
        conn = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(connector=conn) as session:
            plays_json = await return_url_as_json(session, LIVE_GAME_URL.format(gamePk))

        # For every play that has been returned
        for event in plays_json["liveData"]["plays"]["allPlays"]:

            # Has this play already been logged?
            if event["about"]["eventIdx"] in data[gamePk]["plays"]:

                # Already exists so update the play if necessary
                # play already exists, update any necessary info
                if data[gamePk]["plays"][event["about"]["eventIdx"]]["eventTypeId"] != event["result"]["eventTypeId"]:

                    # Checking to see if the eventTypeId has changed
                    data[gamePk]["plays"][event["about"]["eventIdx"]]["eventTypeId"] = event["result"]["eventTypeId"]
                    data[gamePk]["plays"][event["about"]["eventIdx"]]["posted"] = "edit"

                if data[gamePk]["plays"][event["about"]["eventIdx"]]["description"] != event["result"]["description"]:

                    # Checking to see if the description has changed
                    data[gamePk]["plays"][event["about"]["eventIdx"]]["description"] = event["result"]["description"]
                    data[gamePk]["plays"][event["about"]["eventIdx"]]["posted"] = "edit"

            else:
                # play doesn't exist, add it
                data[gamePk]["plays"][event["about"]["eventIdx"]] = {
                    "eventIdx": event["about"]["eventIdx"],
                    "eventTypeId": event["result"]["eventTypeId"],
                    "description": event["result"]["description"],
                    "discord_message_id": -1,
                    "posted": "new"
                }
        
        # Now that we've updated our internal memory, post/update necessary plays         
        # For every play that we have in our memory
        for i in range(len(data[gamePk]["plays"])):
            
            # Is the play new or posted?
            if data[gamePk]["plays"][i]["posted"] == "new":

                # Play is new, post it
                new_message = await data[gamePk]["discord_channel_obj"].send(data[gamePk]["plays"][i]["description"])
                data[gamePk]["plays"][i]["discord_message_obj"] = new_message
                data[gamePk]["plays"][i]["posted"] = "posted"
            
            elif data[gamePk]["plays"][i]["posted"] == "edit":

                # Update the play
                await data[gamePk]["plays"][i]["discord_message_obj"].edit(content=data[gamePk]["plays"][i]["description"])
                data[gamePk]["plays"][i]["posted"] = "posted"
    
        # Now that all the plays are posted, check to see if the game is over
        if plays_json["gameData"]["status"]["detailedState"] == "Final":

            # Game is over
            # If this is the first time the game has been reported as "over", set up the deletion time.
            if data[gamePk]["datetime_to_delete"] == datetime.datetime(1970,1,1,0,0,0):

                # Datetime to delete isn't set, so therefore we must calculate it
                data[gamePk]["datetime_to_delete"] = datetime.datetime.now() + datetime.timedelta(hours=1)

            # Sleep for the allotted time
            await asyncio.sleep((data[gamePk]["datetime_to_delete"] - datetime.datetime.now()).total_seconds())

            # Delete the channel
            await data[gamePk]["discord_channel_obj"].delete()

            # Remove from dictionary
            data.pop(gamePk)

            # Break out of loop
            break
        
        else:
            # Game isn't over, sleep and poll again
            # TODO: Try running 1 second poll time when 13 games are up.
            await asyncio.sleep(1)


async def return_url_as_json(session_obj, url):
    while True:
        async with session_obj.get(url) as response:
            print("[" + str(response.status) + "] " + url)
            if response.status != 200:
                print("Didn't get a 200, sleeping.")
                await asyncio.sleep(10)
            else:
                return json.loads(await response.text())


@client.event
async def on_ready():
    
    print("READY!")
    client.loop.create_task(no_data())
                

with open("token.data", "r") as f:
    client.run(f.read())