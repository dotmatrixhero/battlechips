
import challonge
import discord
import os
import datetime
import google.cloud.logging
import logging
from google.cloud import firestore
from pytz import timezone
from fighting_game import FightingGame
from collections import Counter

# Add a new document
db = firestore.Client()

# Instantiates a client
log_client = google.cloud.logging.Client()

# Retrieves a Cloud Logging handler based on the environment
# you're running in and integrates the handler with the
# Python logging module. By default this captures all logs
# at INFO level and higher
log_client.get_default_handler()
log_client.setup_logging()

logging.info("Initializing bot")
# Tell pychal about your [CHALLONGE! API credentials](http://api.challonge.com/v1).
challonge.set_credentials("YOUR CHALLONGE API NAME","CHALLONGE PASSWORD")

fg = FightingGame()

class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def on_raw_reaction_remove(self, payload):
        print(payload.user_id)
        print(payload.message_id)
        print(payload.emoji.name)
        channel = payload.channel_id

        emojis = ["🔵", "🔴", "⭐", "⬅️", "➡️", "0⃣", "1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣", "🔟", "❌",
                  "✅"]
        # don't check emoji yet, check message_id against fg-hands-fights (and if active) - if there's a match, then we
        # check the emoji for the X or check mark.
        if payload.emoji.name in emojis:
            h_fg_doc = db.collection(u'fg-hands-fights').document(str(payload.message_id)).get()
            if h_fg_doc.exists:
                channel_obj = await self.fetch_channel(channel)
                hands_fight = h_fg_doc.to_dict()
                fd_doc = db.collection(u'fg-fights').document(hands_fight["fight-id"]).get()
                fight_data = fd_doc.to_dict()
                if payload.emoji.name == "❌":
                    await fg.clear_turn_plan_and_rerender_hand_embed(self, db, hands_fight["fight-id"], fight_data,
                                                                     hands_fight["player"], hands_fight["turn-confirmation-message-id"],
                                                                     payload, channel_obj)

                # elif check for green
                elif payload.emoji.name == "✅":
                    await fg.render_turn_submitted_success(self, db, fight_data, hands_fight["fight-id"], hands_fight["player"])
                    # await channel_obj.send("Turn submitted! (Not really)")
                else:

                    await fg.update_based_on_hand_embed_button_press(self, db, str(payload.message_id), channel_obj, channel, hands_fight, payload.emoji.name)

    async def on_raw_reaction_add(self, payload):
        admin = None
        print(payload.user_id)
        print(payload.message_id)
        print(payload.emoji.name)
        channel = payload.channel_id

        emojis = ["🔵", "🔴", "⭐", "⬅️", "➡️", "0⃣", "1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣", "🔟", "❌",
                  "✅"]
        # don't check emoji yet, check message_id against fg-hands-fights (and if active) - if there's a match, then we
        # check the emoji for the X or check mark.
        if payload.emoji.name in emojis:
            h_fg_doc = db.collection(u'fg-hands-fights').document(str(payload.message_id)).get()
            if h_fg_doc.exists:
                channel_obj = await self.fetch_channel(channel)
                hands_fight = h_fg_doc.to_dict()
                fd_doc = db.collection(u'fg-fights').document(hands_fight["fight-id"]).get()
                fight_data = fd_doc.to_dict()
                if payload.emoji.name == "❌":
                    await fg.clear_turn_plan_and_rerender_hand_embed(self, db, hands_fight["fight-id"], fight_data,
                                                                     hands_fight["player"], hands_fight["turn-confirmation-message-id"],
                                                                     payload, channel_obj)
                # elif check for green
                elif payload.emoji.name == "✅":
                    await fg.render_turn_submitted_success(self, db, fight_data, hands_fight["fight-id"], hands_fight["player"])
                    #await channel_obj.send("Turn submitted! (Not really)")
                else:

                    await fg.update_based_on_hand_embed_button_press(self, db, payload.message_id, channel_obj, channel, hands_fight, payload.emoji.name)

            # if check mark we go to mark turn submitted
            # if x reset
            # else try to handle it in update_based_on_hand_embed

        if payload.emoji.name == "🛑" :
            admins_ref = db.collection(u'admins').document(str(payload.user_id))
            doc = admins_ref.get()
            if doc.exists:
                admin = doc.to_dict()["name"]
                if admin:
                    match_messages = db.collection(u'match-messages').document(str(payload.message_id))
                    mdoc = match_messages.get()
                    if mdoc.exists and not mdoc.to_dict()["vote"]:
                        doc_dic = mdoc.to_dict()
                        print(channel)
                        channel_obj = await self.fetch_channel( channel)
                        msg = await channel_obj.fetch_message(payload.message_id)

                        one_count = 0
                        two_count = 0
                        for reaction in msg.reactions:
                            if reaction.emoji == "1⃣":
                                one_count = reaction.count
                            if reaction.emoji == "2⃣":
                                two_count = reaction.count

                        match_id = doc_dic["match"]
                        match_letter = doc_dic["identifier"]
                        winner = "tie"

                        con1 = ""
                        con2 = ""
                        check_for_final = False
                        try:
                            con1 = msg.embeds[0].fields[0].value
                            con2 = msg.embeds[0].fields[1].value
                            check_for_final = "BK" in match_letter
                        except Exception as e:
                            print(e)

                        win_text = "LOL NOBODY"
                        if one_count > two_count:
                            winner = doc_dic["p1"]
                            win_text = con1
                        if one_count < two_count:
                            winner = doc_dic["p2"]
                            win_text = con2

                        await channel_obj.send("<@{0}> has stopped the vote for Match {1}! Final vote tally:\n Contender one *({4})*: {2}\n Contender two *({5})*: {3}".format(payload.user_id, match_letter, one_count, two_count, con1, con2))

                        if check_for_final:
                            matches = challonge.matches.index(doc_dic["tournament"])
                            found = False
                            for iter_match in matches:
                                if iter_match and not iter_match["winner_id"]:
                                    found = True
                                    continue
                            if not found:
                                await channel_obj.send(
                                    "🎉🎉🎉🎉🎉🎉 {0} WINS THE TOURNAMENT! 🎉🎉🎉🎉🎉🎉".format(win_text))

                        match_messages.update({u'vote': True, u'winner': winner})
                        try:
                            challonge.matches.update(doc_dic["tournament"], match_id, scores_csv="{0}-{1}".format(one_count, two_count), winner_id= winner)
                        except Exception as e:
                            logging.error(e)
        return

    async def on_message(self, message):
        print('Message from {0.author}: {0.content}'.format(message))
        admin = False
        if message.author == client.user:
            return

        if message.content.startswith('!fg'):

            keywords = message.content.split(' ')
            if len(keywords) == 1 and keywords[0] == "!fg":
                keywords.append("info")
            if keywords[0] == "!fgc":
                card_name = ""
                if len(keywords) == 1:
                    card_name = None
                else:
                    card_name = " ".join(keywords[1:])
                return await message.channel.send(embed=fg.get_cards_help(db, card_name))
            elif keywords[0] == "!fgm":
                m_name = ""
                if len(keywords) == 1:
                    m_name = None
                else:
                    m_name = " ".join(keywords[1:])
                return await message.channel.send(embed=fg.get_mechanics_help(db, m_name))
            elif keywords[0] == "!fgd":
                keywords.insert(0, "blah")
                await self.interact_deck(keywords, message)
            elif keywords[0] != "!fg":
                await message.channel.send("Sorry, command was not recognized. Try `!fg`")

            if keywords[1] == "profile":
                profile = fg.retrieve_or_create_new_profile(db, str(message.author.id), message.author.name)

                if len(keywords) == 2:
                    embed = discord.Embed(title="Your Profile", colour=discord.Colour(0xd0021b),
                                  description="Your Name: {0}\n Your ID: {1}\n".format(profile["name"], profile["id"]),
                                  timestamp=datetime.datetime.now().astimezone(timezone('US/Pacific')))
                    embed.add_field(name="Your Emoji", value="{0}".format(profile["emoji"]))

                    embed.add_field(name="Your Decks", value="{0}".format("\n".join(profile["vs-decks"])), inline=False)
                    embed.set_footer(text="To edit your profile, use `!fg profile edit`")
                    await message.channel.send("Welcome to your profile!" ,embed=embed)
                    return
                else:
                    if keywords[2] == "edit":
                        if len(keywords) == 3:
                            msg_edit = await message.channel\
                                .send("React to this message with an emoji to save it to your profile. To edit your name, use `!fg profile edit <name>`")

                        else:
                            new_name = " ".join(keywords[2:])
                            msg_edit = await message.channel \
                                .send(
                                "Your name will be set as {0}! React to this message with an emoji to save it to your profile.".format(new_name))

                            profile["name"] = new_name
                        profile["edit-emoji-message-id"] = msg_edit.ids
                        db.collection(u'fg-profile').document(u'{0}'.format(str(message.author.id))).set(profile)

            if keywords[1] == "deck":
                await self.interact_deck(keywords, message)

            if keywords[1] == "info":
                if len(keywords) == 2:
                    await message.channel.send("This is help menu!\nTo get info about game mechanics, type `!fg info mechanics` or `!fgm`."
                                               "\nTo get info about cards, type `!fg info cards` or `!fgc`"
                                               "\nTo challenge a user, type `!fg challenge @user`, tagging the user in a shared channel with the bot and that user."
                                               "\nTo accept a challenge, type `!fg accept accept-code`, where accept-code is the special code you received from a dm from the bot."
                                               "\nTo view your profile and deck names, type `!fg profile`."
                                               "\nTo view and modify your currently selected deck, type `!fg deck`."
                                               "\nTo view and manage current games, type `!fg status`.")
                    return
                else:
                    if keywords[2] == "mechanics":
                        card_name = ""
                        if len(keywords) == 3:
                            card_name = None
                        else:
                            card_name = " ".join(keywords[3:])
                        return await message.channel.send(embed=fg.get_mechanics_help(db, card_name))
                    if keywords[2] == "cards":
                        m_name = ""
                        if len(keywords) == 3:
                            m_name = None
                        else:
                            m_name = " ".join(keywords[3:])
                        return await message.channel.send(embed=fg.get_cards_help(db, m_name))

            # !fg status
            if keywords[1] == "status":
                ref = db.collection(u'fg-player-fights').document(u'{0}'.format(str(message.author.id)))
                udoc = ref.get()
                if not udoc.exists:
                    return await message.channel.send("You have no requests, active games, or match history!\n"
                                                      "Type `!fg info` to learn how to start a game!")
                else:
                    player_info = udoc.to_dict()

                    msg_array = []
                    active = player_info["active-fights"]

                    if len(active) > 0:
                        msg_array.append("\n**Your Active Fights**")
                    for u in active.keys():
                        refp = db.collection(u'fg-profile').document(u'{0}'.format(str(u)))
                        profdoc = refp.get()
                        if not profdoc.exists:
                            await message.channel.send("You have some corrupted data with a broken user! Oops!")

                        msg_array.append(
                            "+ Fight {0} VS {1}".format(active[str(u)], profdoc.to_dict()["name"])
                        )
                    history = player_info["complete-fights"]
                    incoming = player_info["requests"]["incoming"]
                    outgoing = player_info["requests"]["outgoing"]

                    if len(history) > 0:
                        msg_array.append("\n**Your Match History**")
                    for user_id in history.keys():
                        array_hist = history[str(user_id)]
                        refp = db.collection(u'fg-profile').document(u'{0}'.format(str(user_id)))
                        profdoc = refp.get()
                        if not profdoc.exists:
                            await message.channel.send("You have some corrupted data with a broken user! Oops!")


                        win_rate = 0
                        games = 0
                        for match_against_user in array_hist:
                            games = games + 1
                            fight = match_against_user["fight-id"]
                            winner = match_against_user["winner-id"]
                            if str(winner) == str(user_id):
                                winner = profdoc.to_dict()["name"]

                            else:
                                winner = "<@{0}>".format(winner)
                                win_rate = win_rate + 1
                            """
                            if winner != "tie":
                                msg_array.append(
                                    "    + Fight {0}: {1} won!".format(fight, winner))
                            else:
                                msg_array.append(
                                    "    + Fight {0}: Tie!".format(fight, winner))
                            """
                        msg_array.append(
                            "+ User: {}: Win rate: {:.1%}".format(profdoc.to_dict()["name"], win_rate/games)
                        )

                    if len(incoming) > 0:
                        msg_array.append("\n**Your Incoming Challenges**")
                    for incoming_user_id in incoming.keys():
                        in_req = incoming[str(incoming_user_id)]
                        refp = db.collection(u'fg-profile').document(u'{0}'.format(str(incoming_user_id)))
                        profdoc = refp.get()
                        if not profdoc.exists:
                            return await message.channel.send("You have some corrupted data with a broken user! Oops!")

                        in_sent_at = in_req["sent"]
                        in_sent_channel = in_req["request-channel"]
                        msg_array.append("+ {0}: Sent on <#{1}> at {2}\n    Accept Code: {3}".format(profdoc.to_dict()["name"], in_sent_channel, in_sent_at, incoming_user_id))

                    if len(outgoing) > 0:
                        msg_array.append("\n**Your Outgoing Challenges**")
                    for outgoing_user_id in outgoing.keys():
                        out_req = outgoing[str(outgoing_user_id)]
                        refp = db.collection(u'fg-profile').document(u'{0}'.format(str(outgoing_user_id)))
                        profdoc = refp.get()
                        if not profdoc.exists:
                            return await message.channel.send("You have some corrupted data with a broken user! Oops!")

                        sent_at = out_req["sent"]
                        sent_channel = out_req["request-channel"]
                        msg_array.append("+ {0}: Sent on <#{1}> at {2}".format(profdoc.to_dict()["name"], sent_channel, sent_at))

                    if msg_array == []:
                        msg_array.append("You have no requests, active games, or match history!\n"\
                                       "Type `!fg info` to learn how to start a game!")
                    return await message.channel.send("\n".join(msg_array))


            # !fg challenge @user
            # request a fight, check if any of current fights contains user
            if keywords[1] == "challenge":

                requestee = ""
                if len(keywords) < 3 or keywords[2].find("<@") != 0:
                    await message.channel.send("Sorry, please tag a user in a shared channel with: `!fg challenge @user-name-here`")
                    return

                requestee = keywords[2].replace("<", "")
                requestee = requestee.replace(">", "")
                requestee = requestee.replace("@", "")
                requestee = requestee.replace("!", "")

                empty_player_fight_meta = {u"active-fights": {}, u"complete-fights":{}, u"requests": {u"incoming":{}, u"outgoing": {}}}
                # check if requestee exists already in outgoing requests or active fights. if not, send dm
                player_fight_meta_ref = db.collection(u'fg-player-fights').document(u'{0}'.format(str(message.author.id)))
                player_fight_meta = player_fight_meta_ref.get()
                if not player_fight_meta.exists:
                    await message.channel.send(
                        "Welcome to the fighting game, <@{0}>!".format(message.author.id))
                    # ask to Create a profile?
                    player_fight_meta_ref.set(empty_player_fight_meta)
                    player_fight_meta = empty_player_fight_meta
                else:
                    player_fight_meta = player_fight_meta.to_dict()
                outgoing = player_fight_meta["requests"]["outgoing"]
                active = player_fight_meta["active-fights"]
                if str(requestee) in outgoing or str(requestee) in active:
                    await message.channel.send(
                        "You already have an outgoing request or active fight to this user!")
                    return
                try:
                    await create_and_send_dm(self, requestee, "You have been challenged to a fight by <@{0}>! To accept, type\n".format(str(message.author.name)))
                    await create_and_send_dm(self, requestee, "!fg accept {0}".format(str(message.author.id)))
                except Exception as e:
                    await message.channel.send(
                        "Sorry, couldn't send a message to the user you challenged! Do they have dm's turned on?")
                    print(repr(e))
                    return

                # create request json
                req = {u"challenger-deckset": "default",
                       u"request-channel": message.channel.id,
                       u"request-message": message.id,
                       u"sent": datetime.datetime.now()
                       }

                # update outgoing request for requester
                player_fight_meta["requests"]["outgoing"][str(requestee)] = req
                player_fight_meta_ref.set(player_fight_meta)

                # update incoming request for requestee
                requestee_fight_meta_ref = db.collection(u"fg-player-fights").document(str(requestee))
                requestee_fight_meta = requestee_fight_meta_ref.get()
                if not requestee_fight_meta.exists:
                    requestee_fight_meta_ref.set(empty_player_fight_meta)
                    requestee_fight_meta = empty_player_fight_meta
                    # ask to create profile?
                else:
                    requestee_fight_meta = requestee_fight_meta.to_dict()

                requestee_fight_meta["requests"]["incoming"][str(message.author.id)] = req
                requestee_fight_meta_ref.set(requestee_fight_meta)

            if keywords[1] == "accept":
                # usually a dm, from the requestee
                if len(keywords) < 3:
                    await message.channel.send("Sorry, please paste in the accept code with: `!fg accept accept-code-here`")
                challenger = str(keywords[2])

                requestee_fight_meta_ref = db.collection(u"fg-player-fights").document(str(message.author.id))
                requestee_fight_meta = requestee_fight_meta_ref.get()
                if not requestee_fight_meta.exists:
                    await message.channel.send(
                        "Sorry, you aren't registered yet. Try challenging someone with `!fg challenge @user!` in a shared channel!")
                    return
                else:
                    requestee_fight_meta = requestee_fight_meta.to_dict()
                challenger_fight_meta_ref = db.collection(u"fg-player-fights").document(str(challenger))
                challenger_fight_meta = challenger_fight_meta_ref.get()
                if not challenger_fight_meta.exists:
                    await message.channel.send(
                        "Sorry, an error occurred - couldn't retrieve outgoing request from the challenger!")
                    return
                else:
                    challenger_fight_meta = challenger_fight_meta.to_dict()

                if challenger not in requestee_fight_meta["requests"]["incoming"]:
                    await message.channel.send(
                        "Sorry, couldn't find an incoming request with that accept-code!")
                    return

                # delete incoming and outgoing requests in fg-player-fights
                req = requestee_fight_meta["requests"]["incoming"].pop(challenger, None)
                req2 = challenger_fight_meta["requests"]["outgoing"].pop(str(message.author.id), None)
                print(challenger_fight_meta["requests"])
                # create fightid
                # channel id + message id of initialized fight -> fight id
                fight_id = "{0}::{1}".format(req[u"request-channel"], req[u"request-message"])

                # update the active fights for both players
                requestee_fight_meta["active-fights"][challenger] = fight_id
                challenger_fight_meta["active-fights"][str(message.author.id)] = fight_id

                # Commit json back
                challenger_fight_meta_ref.set(challenger_fight_meta)
                requestee_fight_meta_ref.set(requestee_fight_meta)

                # start fight
                # TODO: deckset from request and accept param?
                ch_user = await self.fetch_user(int(challenger))
                profile1 = fg.retrieve_or_create_new_profile(db, str(challenger), ch_user.name)
                profile2 = fg.retrieve_or_create_new_profile(db, str(message.author.id), message.author.name)
                if "current-deck" in profile1 and not profile1["current-deck"] == "default" and profile1["current-deck"] in profile1["vs-decks"] and \
                        "valid" in profile1["vs-decks"][profile1["current-deck"]] and profile1["vs-decks"][profile1["current-deck"]]["valid"]:
                    p1_deck = profile1["current-deck"]
                    p1_str = p1_deck
                else:
                    p1_deck = None
                    p1_str = "default"
                if "current-deck" in profile2 and not profile2["current-deck"] == "default" and profile2["current-deck"] in profile2["vs-decks"] and \
                        "valid" in profile2["vs-decks"][profile2["current-deck"]] and profile2["vs-decks"][profile2["current-deck"]]["valid"]:
                    p2_deck = profile2["current-deck"]
                    p2_str = p2_deck
                else:
                    p2_deck = None
                    p2_str = "default"
                await message.channel.send("Starting a game! \nP1: {0} with deck {1}\nVS\nP2: {2} with deck {3}".format(profile1["name"], p1_str, profile2["name"], p2_str))

                await fg.start_new_vs_fight(db, fight_id, self, challenger, str(message.author.id), req[u"request-channel"], p1_deck, p2_deck)

        if message.content.startswith('!battlechips'):

            id = message.content.split(' ')
            tournament = None
            try:

                tourneys_ref = db.collection(u'tourneys').document(id[1])
                doc = tourneys_ref.get()

                if doc.exists:
                    id[1] = doc.to_dict()["id"]
                tournament = challonge.tournaments.show(id[1])
                print(id)

                # Tournaments, matches, and participants are all represented as normal Python dicts.
                print(tournament["id"])  # 3272
                await message.channel.send("Retrieved data for {0}!".format(tournament["name"]) ) # My Awesome Tournament
            except Exception as e:
                logging.error(e)
                await message.channel.send("Couldn't find that tourney, sorry!")

            try:

                # Retrieve the participants for a given tournament.
                participants = challonge.participants.index(tournament["id"])
                matches = challonge.matches.index(tournament["id"])
                # print(len(participants))  # 13
                # print(matches)
                try:
                    if id[2] is None:
                        display_number = len(matches)
                    else:
                        display_number = int(id[2])

                    x = 0
                    for z in range(0, display_number):
                        match = matches[z]
                        while match and match["winner_id"]:
                            x = x + 1
                            match = matches[x]
                        if not match:
                            await message.channel.send("That's all the unfinished matches I could find!")
                            return
                        embed = format_match(tournament["id"], match)
                        sent_msg = await message.channel.send(embed=embed)
                        emojis = ["1⃣", "2⃣"]
                        for emoji in emojis:
                            try:
                                await sent_msg.add_reaction(emoji)
                            except Exception as e:
                                logging.warning(e)
                        record_match_message(sent_msg, match["id"], match["identifier"], match["player1_id"],
                                             match["player2_id"], tournament["id"])
                except ValueError as e:
                    found = False
                    for match in matches:
                        if match["identifier"] == id[2]:
                            found = True
                            embed = format_match(tournament["id"], match)
                            sent_msg = await message.channel.send(embed=embed)
                            emojis = ["1⃣", "2⃣"]
                            for emoji in emojis:
                                try:
                                    await sent_msg.add_reaction(emoji)
                                except Exception as e:
                                    logging.warning(e)
                            record_match_message(sent_msg, match["id"], match["identifier"], match["player1_id"],
                                                 match["player2_id"], tournament["id"])
                            return
                    if not found:
                        await message.channel.send("Couldn't recognize your second argument! Sorry!")

            except Exception as e:
                logging.error(e)
                await message.channel.send("There was an error processing the data. Sorry!")

    async def interact_deck(self, keywords, message):
        profile = fg.retrieve_or_create_new_profile(db, str(message.author.id), message.author.name)
        if len(keywords) == 2:
            if "current-deck" not in profile or profile["current-deck"] == "default":
                await message.channel.send("You haven't selected a deck yet! The default deck will be selected.")

            await self.print_deck_messages(profile, message)
            db.collection(u'fg-profile').document(u'{0}'.format(str(message.author.id))).set(profile)
            return
        else:
            if keywords[2] == "create-deck":
                if len(keywords) > 3:
                    # disallow 'default' as name,
                    for n in keywords[3:]:
                        if not n.isalnum():
                            return await message.channel.send(
                                "Please use an alphanumeric name for your deck (spaces are allowed)")

                    deck_name = " ".join(keywords[3:])
                    if deck_name in profile["vs-decks"] or deck_name == "default":
                        return await message.channel.send(
                            "That deck already exists! You can remove it with `!fg delete-deck {0}` You can't delete the default deck, though!".format(deck_name))
                    profile["vs-decks"][deck_name] = {"options": [], "pressure": [], "valid": False}
                    profile["current-deck"] = deck_name
                    if not "edit-deck-message-id" in profile or not "edit-deck-message-id2" in profile:
                        await self.print_deck_messages(profile, message)
                    await message.channel.send(
                        "Deck created! You've switched decks to an empty one - please edit it with \n"
                        "`!fg deck add <card name>` and `!fg deck remove <card name>`")
                    db.collection(u'fg-profile').document(u'{0}'.format(str(message.author.id))).set(profile)
                else:
                    return await message.channel.send(
                        "Type `!fg deck add <card name>` or `!fg deck remove <card name>` to edit your deck.\n"
                        "Create a new, blank deck with `!fg deck create-deck <deck name>` (only alphanumerics, please)\n"
                        "To delete a deck, type `!fg deck delete-deck <deck name>`.\n"
                        "To select a different deck for playing/modifying with cards, type `!fg deck select-deck <deck name>`")
            if keywords[2] == "delete-deck":
                if len(keywords) > 3:
                    deck_name = " ".join(keywords[3:])
                    if not deck_name in profile["vs-decks"]:
                        return await message.channel.send(
                            "That deck does not exist. You can list your deck names with `!fg profile`".format(
                                deck_name))
                    else:
                        profile["vs-decks"].pop(deck_name, None)
                        if profile["current-deck"] == deck_name:
                            profile.pop("current-deck", None)
                        db.collection(u'fg-profile').document(u'{0}'.format(str(message.author.id))).set(profile)
                        return await message.channel.send(
                            "Deck {0} was deleted.".format(deck_name))
                else:
                    return await message.channel.send(
                        "Type `!fg deck add <card name>` or `!fg deck remove <card name>` to edit your deck.\n"
                        "Create a new, blank deck with `!fg deck create-deck <deck name>` (only alphanumerics, please)\n"
                        "To delete a deck, type `!fg deck delete-deck <deck name>`.\n"
                        "To select a different deck for playing/modifying with cards, type `!fg deck select-deck <deck name>`")
            if keywords[2] == "add" or keywords[2] == "remove":
                if len(keywords) > 3:
                    card_name = " ".join(keywords[3:])
                    c = fg.get_card_data(db, card_name=card_name)
                    if c:
                        if "current-deck" not in profile or profile["current-deck"] == "default":
                            return await message.channel.send(
                                "You can't edit a deck because you haven't selected a deck yet! Create a deck or select one.")
                        # retrieve deck edit-deck-message-id, if its not there, add it
                        if "edit-deck-message-id" not in profile or "edit-deck-message-id2" not in profile:
                            await self.print_deck_messages(profile, message)
                        deckz = None
                        try:
                            render = []
                            deckz = profile["vs-decks"][profile["current-deck"]]
                            if c["deck"] == "pressure":
                                deckz_specific = deckz["pressure"]
                            else:
                                deckz_specific = deckz["options"]
                            if keywords[2] == "add":
                                deckz_specific.append({"name": c["name"]})
                            elif keywords[2] == "remove":
                                found = False
                                for i in deckz_specific:
                                    if i["name"] == c["name"]:
                                        deckz_specific.remove(i)
                                        found = True
                                        break
                                if not found:
                                    raise Exception("Couldn't find that card in your deck")
                            do = await self.check_is_deck_valid_and_return_sorted(deckz["options"], profile["unlocked"])
                            dp = await self.check_is_deck_valid_and_return_sorted(deckz["pressure"],
                                                                                  profile["unlocked"])
                            deckz["valid"] = True
                            ch_obj = await self.fetch_channel(int(profile["edit-deck-channel"]))
                            if c["deck"] == "pressure":
                                msge_edit = await ch_obj.fetch_message(int(profile["edit-deck-message-id"]))
                                msge_edit.embeds[0].clear_fields()
                                for p in dp:
                                    fg.render_compact_card_in_one_embed(msge_edit.embeds[0], p, platonic=True)
                            else:  # c["deck"] == "options":
                                msge_edit = await ch_obj.fetch_message(int(profile["edit-deck-message-id2"]))
                                msge_edit.embeds[0].clear_fields()
                                for o in do:
                                    fg.render_compact_card_in_one_embed(msge_edit.embeds[0], o, emoji=None,
                                                                        platonic=True)
                            await msge_edit.edit(embed=msge_edit.embeds[0])

                            await message.channel.send(
                                "Deck modified.")
                            if len(deckz["options"]) < 10 or len(deckz["options"]) > 25:
                                deckz["valid"] = False
                                raise Exception(
                                    "Your options deck is invalid due to length! Each deck (pressure and options) must have more than 10 cards and less than 25.")
                            if len(deckz["pressure"]) < 10 or len(deckz["pressure"]) > 25:
                                deckz["valid"] = False
                                raise Exception(
                                    "Your pressure deck is invalid due to length! Each deck (pressure and options) must have more than 10 cards and less than 25.")
                        except Exception as e:
                            error_msg = e.args[0]
                            if deckz and "valid" in deckz:
                                deckz["valid"] = False
                                if "invalid due to length" in error_msg:
                                    await message.channel.send(
                                        "**Warning.**\nYou're still building your deck, so you won't be able to play with it.\n"
                                        "{0}".format(error_msg))
                                else:
                                    return await message.channel.send(
                                        "**Warning.**\nYour deck is not valid yet, so you won't be able to play with it.\n"
                                        "{0}".format(error_msg))

                        db.collection(u'fg-profile').document(
                            u'{0}'.format(str(message.author.id))).set(
                            profile)
                        # check if valid deck, if so set valid.
                    else:
                        await  message.channel.send(
                            "**Warning.**\nCouldn't find the cards you're referencing!")
            if keywords[2] == "select-deck":
                if len(keywords) > 3:
                    deck_name = " ".join(keywords[3:])
                    if not deck_name in profile["vs-decks"] and not deck_name == "default":
                        return await message.channel.send(
                            "That deck does not exist. You can list your deck names with `!fg profile`".format(
                                deck_name))
                    else:
                        profile["current-deck"] = deck_name
                        await message.channel.send("{0} deck selected.".format(deck_name))
                        await self.print_deck_messages(profile, message)
                        db.collection(u'fg-profile').document(u'{0}'.format(str(message.author.id))).set(
                            profile)
                else:

                    unlocked_embed = discord.Embed(title="Select a deck", colour=discord.Colour(0xd0021b),
                                                   description="Type `!fg deck add <card name>` or `!fg deck remove <card name>` to edit your deck.\n"
                                                               "Create a new, blank deck with `!fg deck create-deck <deck name>` (only alphanumerics, please)\n"
                                                               "To delete a deck, type `!fg deck delete-deck <deck name>`.\n"
                                                               "To select a different deck for playing/modifying with cards, type `!fg deck select-deck <deck name>`\n"
                                                               "Your decks are listed below.")
                    for deck in profile["vs-decks"]:
                        presh = [p["name"] for p in profile["vs-decks"][deck]["pressure"]]
                        opts = [p["name"] for p in profile["vs-decks"][deck]["options"]]
                        unlocked_embed.add_field(name="{0}".format(deck), value="Deck valid: {0}\n"
                                                                                "--Pressure cards--\n{1}\n"
                                                                                "--Options cards--\n{2}".format(
                            profile["vs-decks"][deck]["valid"],
                            "\n".join(presh),
                            "\n".join(opts)))
                    return await message.channel.send(embed=unlocked_embed)

    async def print_deck_messages(self, profile, message):
        deckz = None
        if "current-deck" not in profile or profile["current-deck"] not in profile["vs-decks"] or profile["current-deck"] == "default":
            await message.channel.send("Whoa, You haven't selected a deck yet. Please select or create a new deck.\n"
                                       "In the mean time, here's the default deck! \n(You can't add or remove cards from this one)")
            deckz = fg.get_default_decks(db)
            deck_name = "default"
        else:
            deckz = profile["vs-decks"][profile["current-deck"]]

            deck_name = profile["current-deck"]
        if "valid" in deckz and deckz["valid"]:
            val = "a valid"
            val2 = "It can be played with now when you challenge a player!"
        else:
            val = "an invalid"
            val2 = "It cannot be played right now, and starting a game will make you select the default deck!"

        unlocks = []
        docs = db.collection('fg-cards').stream()
        cache_cards = {}
        for doc in docs:
            if doc.get("set") == "base":
                unlocks.append(doc.to_dict())
            cache_cards[doc.get("name")] = doc.to_dict()

        display_unlock_array = []
        for unlock in sorted(profile["unlocked"]):
            if unlock in cache_cards:
                c_data = cache_cards[unlock]
                unlocks.append(c_data)

        unlocks.sort(key=lambda x: x["mana"] - 1000 if "rarity" not in x or x["rarity"] == "basic" else (x["mana"] if x["rarity"] == "special" else x["mana"] + 1000))

        basic_msg = ""
        special_msg = ""
        ult_msg = ""

        for c_data in unlocks:
            if "rarity" not in c_data or c_data["rarity"] == "basic":
                if basic_msg is not None:
                    basic_msg = "Basic Cards (3 max per deck)--\n"
                    display_unlock_array.append(basic_msg)
                    basic_msg = None
                display_unlock_array.append(" > {0} {2} / Cost: {1} \n".format(c_data["name"], c_data["mana"],
                                                                                  c_data["image"],
                                                                                  c_data["description"], c_data["deck"]))
            if "rarity" in c_data and c_data["rarity"] == "special":
                if special_msg is not None:
                    special_msg = "Special Cards (2 max per deck)--\n"
                    display_unlock_array.append(special_msg)
                    special_msg = None
                display_unlock_array.append(
                    " > {0} {2} / Cost: {1} \n".format(c_data["name"],
                                                                                            c_data["mana"],
                                                                                            c_data["image"],
                                                                                            c_data["description"],
                                                                                            c_data["deck"]))
            if "rarity" in c_data and c_data["rarity"] == "ultimate":
                if ult_msg is not None:
                    ult_msg = "Ultimate Cards (1 max per deck)--\n "
                    display_unlock_array.append(ult_msg)
                    ult_msg = None
                display_unlock_array.append(
                    " > {0} {2} / Cost: {1} \n".format(c_data["name"],
                                                c_data["mana"],
                                                c_data["image"],
                                                c_data["description"],
                                                c_data["deck"]))


        unlocked_embed = discord.Embed(title="Your Unlocked Cards", colour=discord.Colour(0xd0021b), description="{0}".format("".join(display_unlock_array)))

        embed = discord.Embed(title="Deck {0}: Pressure".format(deck_name), colour=discord.Colour(0xd0021b),
                              description="**Your currently selected deck is `{0}`! It is {1} deck. {2}!**\n"
                                          "Type `!fg deck add <card name>` or `!fg deck remove <card name>` to edit your deck.\n"
                                          "Create a new, blank deck with `!fg deck create-deck <deck name>` (only alphanumerics, please)\n"
                                          "To delete a deck, type `!fg deck delete-deck <deck name>`.\n"
                                          "To select a different deck for playing/modifying with cards, type `!fg deck select-deck <deck name>`".format(
                                  deck_name, val, val2),
                              timestamp=datetime.datetime.now().astimezone(timezone('US/Pacific')))

        embed2 = discord.Embed(title="Deck {0}: Options".format(deck_name),
                               colour=discord.Colour(0xd0021b),
                               timestamp=datetime.datetime.now().astimezone(timezone('US/Pacific')))
        if len(unlocks) > 25:
            limit = True
            unlocked_embed.set_footer(text="You have more than 25 unlocked cards! Hit the arrow button to see more!")
        else:
            limit = False

        counter = 0
        for card_compact in unlocks:
            fg.render_compact_card_in_one_embed(unlocked_embed, card_compact, platonic=True)
            if limit and counter > 24:
                break
            counter = counter + 1

        for o in deckz["options"]:
            fg.render_compact_card_in_one_embed(embed2, cache_cards[o["name"]], emoji=None, platonic=True)
        for p in deckz["pressure"]:
            fg.render_compact_card_in_one_embed(embed, cache_cards[p["name"]], emoji=None, platonic=True)
        unlocked_msg = await message.channel.send(embed=unlocked_embed)
        deck_msg = await message.channel.send(embed=embed)
        deck_msg2 = await message.channel.send(embed=embed2)

        profile["unlocked-message-id"] = unlocked_msg.id
        profile["edit-deck-message-id"] = deck_msg.id
        profile["edit-deck-message-id2"] = deck_msg2.id
        profile["edit-deck-channel"] = message.channel.id

    async def check_is_deck_valid_and_return_sorted(self, deck, unlocked):
        # sort arrays
        deck_sorted = []
        # check length of arrays, between 10 and 25.
        counter = None
        for name in deck:
            # get card data from name
            c = fg.get_card_data(db, card_name=name["name"])
            if c is not None:
                deck_sorted.append(c)
                if c["name"] in sorted(unlocked) or ("set" not in c or c["set"] == "base"):
                    if "rarity" not in c:
                        c["rarity"] = "basic"
                    if c["rarity"] == "basic":
                        limit = 3
                    elif c["rarity"] == "special":
                        limit = 2
                    elif c["rarity"] == "ultimate":
                        limit = 1
                    else:
                        limit = 1
                    if not counter:
                        counter = Counter([x["name"] for x in deck])
                    else:
                        print(counter)
                        if counter[c["name"]] > limit:
                            raise Exception("You can only put {0} {1} card(s) in your deck, since it is a {2} card!"
                                            .format(limit, c["name"], c["rarity"]))
                else:
                    raise Exception("You have a card in your deck that you haven't unlocked yet!\n Card: {0}".format(c["name"]))
            else:
                raise Exception("Couldn't find a card by that name! Use `!fgc` to list cards.")

        deck_sorted.sort(key=lambda x: int(x["mana"])-1000 if "rarity" not in x or x["rarity"] == "basic" else (int(x["mana"]) if x["rarity"] =="special" else int(x["mana"]) + 1000 ))
        return deck_sorted

def format_match(tourney_id, match):
    p1 = challonge.participants.show(tourney_id, match["player1_id"])
    p2 = challonge.participants.show(tourney_id, match["player2_id"])

    if p1 and p2:
        embed = discord.Embed(title="Match {0}".format(match["identifier"]), colour=discord.Colour(0xe0d25c),
                              description=" Which chip is superior?",
                              timestamp=datetime.datetime.now())

        embed.set_author(name="Battle Chips")
        embed.add_field(name="*Contender :one:*", value="{0}".format(p1["name"]))
        embed.add_field(name="*Contender :two:*", value="{0}".format(p2["name"]))
        return embed

    return None

def record_match_message(sent_msg, match, identifier, p1, p2, tourney_id):
    cities_ref = db.collection(u'match-messages').document("{0}".format(sent_msg.id)).set(
        {u'match': match, u'vote': False, u'identifier': identifier, u'p1': p1, u'p2': p2,
         u'tournament': tourney_id})

async def create_and_send_dm(discord_client, id, msg):
    user = await discord_client.fetch_user(int(id))
    if user.dm_channel is None:
        channel = await user.create_dm()
    else:
        channel = user.dm_channel
    return await channel.send(msg)

client = MyClient()
client.run("DISCORD API KEY")



