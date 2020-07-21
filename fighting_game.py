
import discord
import datetime
import logging
import random
import copy
from pytz import timezone

from google.cloud import firestore

class FightingGame():

    def update_profile(self):
        # i'm lazy
        pass

    def get_default_decks(self, db):
        ref = db.collection(u'fg-profile').document("default")
        doc = ref.get()
        if doc.exists:
            return doc.to_dict()["vs-decks"]["default"]

    def retrieve_or_create_new_profile(self, db, player_id, player_tag, emoji="😃"):
        ref = db.collection(u'fg-profile').document(str(player_id))
        doc = ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            profile = {
                u'emoji':emoji,
                u'name': player_tag,
                u'id': player_id,
                u'ability':"default",
                u'vs-decks':{},
                u'unlocked':[],
                u'max-hp': 15

            }
            ref.set(profile)
            return profile

    def draw_cards_from_deck(self, player_hand, player_deck, num_cards=1, discard=[], name=""):
        for z in range(0, num_cards):
            if len(player_hand) == 10:
                raise Exception("their hand was full so they could not!")
            if len(player_deck) == 0:
                if len(discard) == 0:
                    raise Exception(
                        "the deck and discard was empty so they could not! (Deck will be reshuffled next round)")
                for dis_card in discard:
                    if dis_card["deck"] == name:
                        print("added")
                        player_deck.append(dis_card)
                discard = []
                random.shuffle(player_deck)
            card = player_deck.pop()
            card["submitted"] = False
            card["current-mana"] = card["mana"]
            player_hand.append(card)


    # based on card name, reference the master card table and copy it to a new game-ready deck
    def create_populated_deck_from_deck_reference_and_shuffle(self, db, deck):
        playable_deck = []
        cache = {}

        for card in deck:
            if card["name"] in cache:
                playable_deck.append(copy.copy(cache[card["name"]]))
            platonic_card = db.collection(u"fg-cards").document(card["name"]).get().to_dict()
            platonic_card["current-mana"] = platonic_card["mana"]
            cache[card["name"]] = platonic_card
            playable_deck.append(copy.copy(platonic_card))
        random.shuffle(playable_deck)
        return playable_deck

    async def start_new_vs_fight(self, db, fight_id, discord_client, p1, p2, spec_channel, p1_deckset_key=None, p2_deckset_key=None):
        p1_user = await discord_client.fetch_user(int(p1))
        p2_user = await discord_client.fetch_user(int(p2))
        # create empty profile if none exists
        p1_profile = self.retrieve_or_create_new_profile(db, p1, p1_user.name)
        p2_profile = self.retrieve_or_create_new_profile(db, p2, p2_user.name)

        if len(p1_profile["vs-decks"]) == 0 or p1_deckset_key is None:
            default_decks = self.get_default_decks(db)
            pd1 = default_decks["pressure"]
            od1 = default_decks["options"]
        else:
            p1_deckset = p1_profile["vs-decks"][p1_deckset_key]
            pd1 = p1_deckset["pressure"]
            od1 = p1_deckset["options"]

        if len(p2_profile["vs-decks"]) == 0 or p2_deckset_key is None:
            default_decks = self.get_default_decks(db)
            pd2 = default_decks["pressure"]
            od2 = default_decks["options"]
        else:
            p2_deckset = p2_profile["vs-decks"][p2_deckset_key]
            pd2 = p2_deckset["pressure"]
            od2 = p2_deckset["options"]

        # in the future maybe have the status update depending on player ability, etc.

        p1_pressure_deck = self.create_populated_deck_from_deck_reference_and_shuffle(db, pd1)
        p1_options_deck = self.create_populated_deck_from_deck_reference_and_shuffle(db, od1)

        p2_pressure_deck = self.create_populated_deck_from_deck_reference_and_shuffle(db, pd2)
        p2_options_deck = self.create_populated_deck_from_deck_reference_and_shuffle(db, od2)

        p1_hand = []
        self.draw_cards_from_deck(p1_hand, p1_pressure_deck, 3, [], name="pressure")
        self.draw_cards_from_deck(p1_hand, p1_options_deck, 3, [], name="options")

        p2_hand = []
        self.draw_cards_from_deck(p2_hand, p2_pressure_deck, 3, [], name="pressure")
        self.draw_cards_from_deck(p2_hand, p2_options_deck, 3, [],name="options")


        p1_data = {
            u'id': int(p1),
            u'position': 4,
            u'status': {},
            u'mana': 1,
            u'current-hp': p1_profile["max-hp"],
            u'max-hp': p1_profile["max-hp"],
            u'player': {
                u'name': p1_profile["name"],
                u'emoji': p1_profile["emoji"],
                u'ability': p1_profile["ability"]
            },
            u'hand': p1_hand,
            u'pressure-deck': p1_pressure_deck,
            u'options-deck': p1_options_deck,
            u'next-turn':{
                u'actions-submitted': False,
                u'reveal': -1,
                u'steps': [],
                u'submitted': False
            },
            u'discard': []
        }
        p2_data = {
            u'id': int(p2),
            u'position': 6,
            u'status': {},
            u'mana': 1,
            u'current-hp': p2_profile["max-hp"],
            u'max-hp': p2_profile["max-hp"],
            u'player': {
                u'name': p2_profile["name"],
                u'emoji': p2_profile["emoji"],
                u'ability': p2_profile["ability"]
            },
            u'hand': p2_hand,
            u'pressure-deck': p2_pressure_deck,
            u'options-deck': p2_options_deck,
            u'next-turn':{
                u'actions-submitted': False,
                u'reveal': -1,
                u'steps': [],
                u'submitted': False
            },
            u'discard': []
        }
        # hand, draw 2 from each deck

        fight_data = {
            u'round': 1,
            u'p1': p1_data,
            u'p2': p2_data,
            u'started': datetime.datetime.now(),
            u'updated': datetime.datetime.now(),
            u'logs': ["---------- **Round 1** ---------"]}

        await self.send_new_fight_messages_and_update_fight_data_with_discord_meta(discord_client, fight_data, p1_user, p2_user, spec_channel)

        db.collection(u'fg-fights').document("{0}".format(fight_id)).set(fight_data)

        p1_reaction_key = fight_data["metadata"]["p1"]["hand_msg"]
        p2_reaction_key = fight_data["metadata"]["p2"]["hand_msg"]

        p1_turn_conf = fight_data["metadata"]["p1"]["turn_confirmation_msg"]
        p2_turn_conf = fight_data["metadata"]["p2"]["turn_confirmation_msg"]
        db.collection(u'fg-hands-fights').document("{0}".format(str(p1_reaction_key))).set({
            u'fight-id': fight_id, u'active': True, u'player': "p1", u'turn-confirmation-message-id': p1_turn_conf
        })
        db.collection(u'fg-hands-fights').document("{0}".format(str(p2_reaction_key))).set({
            u'fight-id': fight_id, u'active': True, u'player': "p2", u'turn-confirmation-message-id': p2_turn_conf
        })


    # this method can be used to re-render a fight if messages were lost, etc.
    async def send_new_fight_messages_and_update_fight_data_with_discord_meta(self, discord_client, fight_data,
                                                                              p1_user, p2_user, spec_channel=None):

        if p1_user.dm_channel is None:
            p1_channel = await p1_user.create_dm()
        else:
            p1_channel = p1_user.dm_channel

        if p2_user.dm_channel is None:
            p2_channel = await p2_user.create_dm()
        else:
            p2_channel = p2_user.dm_channel
        msgdata = {u'p1': {}, u'p2': {}, u'spec': {}}


        p1_embeds = self.render_embeds(fight_data, "p1")
        p2_embeds = self.render_embeds(fight_data, "p2")

        p1_hand_msg = await p1_channel.send(embed=p1_embeds["hand"])
        p2_hand_msg = await p2_channel.send(embed=p2_embeds["hand"])


        p1_turn_confirmation_msg = await p1_channel.send(embed=p1_embeds["turn_confirmation"])
        p2_turn_confirmation_msg = await p2_channel.send(embed=p2_embeds["turn_confirmation"])

        p1_log_msg = await p1_channel.send(embed=p1_embeds["log"])
        p2_log_msg = await p2_channel.send(embed=p2_embeds["log"])
        p1_state_msg = await p1_channel.send(embed=p1_embeds["fight_state"])
        p2_state_msg = await p2_channel.send(embed=p2_embeds["fight_state"])

        await self.add_controls(p1_hand_msg)
        await self.add_controls(p2_hand_msg)

        msgdata[u'p1'][u'channel'] = int(p1_channel.id)
        msgdata[u'p2'][u'channel'] = int(p2_channel.id)

        msgdata[u'p1'][u'state_msg'] = p1_state_msg.id
        msgdata[u'p2'][u'state_msg'] = p2_state_msg.id

        msgdata[u'p1'][u'log_msg'] = p1_log_msg.id
        msgdata[u'p2'][u'log_msg'] = p2_log_msg.id

        msgdata[u'p1'][u'turn_confirmation_msg'] = p1_turn_confirmation_msg.id
        msgdata[u'p2'][u'turn_confirmation_msg'] = p2_turn_confirmation_msg.id

        msgdata[u'p1'][u'hand_msg'] = p1_hand_msg.id
        msgdata[u'p2'][u'hand_msg'] = p2_hand_msg.id

        if spec_channel:
            chan = await discord_client.fetch_channel(int(spec_channel))
            spec_state_msg = await chan.send(embed=p1_embeds['fight_state'])
            spec_log_msg = await chan.send(embed=p1_embeds['log'])
            msgdata[u'spec'][u'state_message'] = spec_state_msg.id
            msgdata[u'spec'][u'log_msg'] = spec_log_msg.id
            msgdata[u'spec'][u'channel'] = int(spec_channel)

        fight_data[u'metadata'] = msgdata

    def get_cards_help(self, db, card_name=None):
        if card_name:
            doc = self.get_card_data(db, card_name)
            if doc is not None:
                embed = discord.Embed(title="Card Info", colour=discord.Colour(0xd0021b),
                                      description="Here's information about {0}!\n\n".format(card_name))
                self.render_card(embed, doc, None)
                return embed

        docs = db.collection('fg-cards').select(["name", "image"]).stream()
        c_list = []
        for doc in docs:
            c_list.append("{0} {1}".format(doc.get("name"), doc.get("image")))
        embed = discord.Embed(title="Card List", colour=discord.Colour(0xd0021b),
                              description="{0}".format("\n ".join(c_list)))
        return embed

    def get_card_data(self, db, card_name):
        if card_name:
            doc = db.collection('fg-cards').document(card_name).get()
            if doc.exists:
                doc = doc.to_dict()
                return doc
            else:
                docs = db.collection('fg-cards').stream()
                cache_cards = {}
                for zdoc in docs:
                    if zdoc.get("name").lower() == card_name:
                        return zdoc.to_dict()
                return None



    def get_mechanics_help(self, db, mechanic_name=None):
        if mechanic_name:
            doc = db.collection('fg-info').document(mechanic_name).get()
            if doc.exists:
                doc = doc.to_dict()
                embed = discord.Embed(title="Mechanic Info", colour=discord.Colour(0xd0021b),
                                      description="Here's information about {0}!\n\n{1}"
                                      .format(mechanic_name, doc["description"].encode('ascii', 'ignore').decode('unicode_escape')))

                return embed

        docs = db.collection('fg-info').select(["description"]).stream()
        c_list = []
        for doc in docs:
            c_list.append(doc.id)
        embed = discord.Embed(title="Mechanics List", colour=discord.Colour(0xd0021b),
                              description="{0}".format("\n ".join(c_list)))
        return embed

    def predict_game_state_for_solo_stack_step(self, db, step, game_state, player, meta, turn_conf):
        sub_stack_type_order = ["movement", "regeneration", "negate-damage", "counter",
                                "self-debuff", "debuff", "buff", "late-movement", "draw"]
        player_data = game_state[player]
        hand = player_data["hand"]
        return_string = ""
        # keep in mind game state here won't be written back to db (source of truth)

        # raise exceptions if hand size is max and trying to draw,

        # raise exception if you're off-balance and playing an option card

        # raise warning if block could overfill handsize

        # look up verbose-text-future from fg-log-steps table based on card
        step_doc = db.collection(u'fg-log-steps').document(step["name"]).get()
        if not step_doc.exists:
            raise Exception("Step `{0}` was not recognized. Please contact <@116045478709297152>, this is a bug.".format(step["name"]))
        platonic_step = step_doc.to_dict()

        if "name" in step and step["name"] == "card":
            if len(meta["temp-cards"]) > 0:
                card = meta["temp-cards"].pop(0)
            else:
                card = hand[int(step["value"])]
            if card["deck"] == "options":
                if "off-balance" in player_data["status"] and player_data["status"]["off-balance"] > 0:
                    warning = "\n**Warning**\n Based on your current status or future plan, you will be Off-Balance while trying to play this card.\n" \
                              "You cannot play options cards while Off-Balance, so this card will likely be returned to your hand! "
                    turn_conf.append(warning)
                # iterate through hand, discount pressure
                for discount_card in meta["temp-cards"]:
                    if discount_card["deck"] == "pressure" and discount_card["current-mana"] > 1:
                        discount_card["current-mana"] = discount_card["current-mana"] -1
                for discount_card in hand:
                    if discount_card["deck"] == "pressure" and discount_card["current-mana"] > 1:
                        discount_card["current-mana"] = discount_card["current-mana"] - 1
            return_string = return_string + "\n• " + platonic_step["verbose-text-future"].format(card["name"], "You")
            return_string = "{0} for {1} mana.".format(return_string, card["current-mana"])

            # Buff the card
            if "next-card-shatter" in player_data["status"] and player_data["status"]["next-card-shatter"] > 0:
                if "damage" in card["tags"]:
                    step["sub-steps"]["shatter"] = 1
                    warning = "This card will apply Shatter if it hits, and use up your next card shatter buff!"
                    turn_conf.append(warning)
                    player_data["status"]["next-card-shatter"] = player_data["status"]["next-card-shatter"] - 1

            if "range-buff-2" in player_data["status"] and player_data["status"]["range-buff-2"]["next-cards"] > 0:
                if "damage" in card["tags"]:
                    card["range"] = card["range"] + 2
                    warning = "This card is buffed to have with +2 range!"
                    turn_conf.append(warning)
                    player_data["status"]["range-buff-2"]["next-cards"] = player_data["status"]["range-buff-2"]["next-cards"] - 1

            # raise exceptions if mana is too low/we're betting on mana discounts later
            for effect in step["sub-steps"]:
                # sort substeps so they are processed in the right order
                substep_doc = db.collection(u'fg-log-steps').document(effect).get()
                if not substep_doc.exists:
                    raise Exception("Step `{0}` was not recognized. Please contact <@116045478709297152>, this is a bug.".format(effect))
                platonic_step2 = substep_doc.to_dict()
                if platonic_step2["type"] == "movement":
                    try:
                        return_string = self.handle_future_movement(game_state, player, effect,
                                                                    step["sub-steps"][effect],
                                                                    platonic_step2, return_string, turn_conf, True)
                    except Exception as e:
                        error_msg = e.args[0]
                        if error_msg == "rooted_warning":
                            error_msg = ""
                            warning = "**You are rooted, so the movement effect of this card will probably not work!**"
                            turn_conf.append(warning)
                        elif error_msg == "wall move error":
                            error_msg = ""
                            warning = "\n**Warning**\n You probably won't move, since you're against a wall! "
                            turn_conf.append(warning)
                        else:
                            raise e
                if platonic_step2["type"] == "regeneration":
                    return_string = self.handle_future_regeneration(game_state, player, effect, step["sub-steps"][effect],
                                                    platonic_step2, return_string, turn_conf, True)
                if platonic_step2["type"] == "negate-damage":
                    return_string = self.handle_future_negate_damage(game_state, player, effect, step["sub-steps"][effect], platonic_step2,
                                               return_string, turn_conf, True)
                if platonic_step2["type"] == "counter":
                    return_string = self.handle_future_counter(game_state, player, effect, step["sub-steps"][effect], platonic_step2,
                                                   return_string, turn_conf, True)
                if platonic_step2["type"] == "damage":
                    return_string = self.handle_future_damage(game_state, player, effect, step["sub-steps"][effect], platonic_step2,
                                                    return_string, turn_conf, True)
                if platonic_step2["type"] == "self-damage":
                    return_string = self.handle_future_damage(game_state, player, effect, step["sub-steps"][effect],
                                                              platonic_step2,
                                                              return_string, turn_conf, True, True)
                if platonic_step2["type"] == "self-debuff":
                    return_string = self.handle_future_self_debuff(game_state, player, effect, step["sub-steps"][effect], platonic_step2,
                                               return_string, turn_conf, True)
                if platonic_step2["type"] == "debuff":
                    return_string = self.handle_future_debuff(game_state, player, effect, step["sub-steps"][effect], platonic_step2,
                                               return_string, turn_conf, True)

                if platonic_step2["type"] == "buff":
                    return_string = self.handle_future_buff(game_state, player, effect, step["sub-steps"][effect], platonic_step2,
                                               return_string, turn_conf, True)
                if platonic_step2["type"] == "opponent-buff":
                    return_string = self.handle_future_opponent_buff(game_state, player, effect, step["sub-steps"][effect], platonic_step2,
                                               return_string, turn_conf, True)
                if platonic_step2["type"] == "late-movement":
                    return_string = self.handle_future_movement(game_state, player, effect, step["sub-steps"][effect], platonic_step2,
                                               return_string, turn_conf, True)
                if platonic_step2["type"] == "draw":
                    return_string = return_string + "\n > • " + platonic_step2["verbose-text-future"].format(step["sub-steps"][effect], "You")
                # also clear negate-damage, interrupted and other temp statuses

            if player_data["mana"] < card["current-mana"]:

                turn_conf.append(return_string)
                player_data["mana"] = player_data["mana"] - card["current-mana"]
                raise Exception("mana_warning")
            player_data["mana"] = player_data["mana"] - card["current-mana"]
            if player == "p1":
                opp_num = "p2"
            else:
                opp_num = "p1"

            if card["range"] > 0 and abs(player_data["position"] - game_state[opp_num]["position"]) > card["range"]:
                turn_conf.append(return_string)
                raise Exception("range_warning")
        else:
            meta["non-card-action-count"] = meta["non-card-action-count"] + 1
            if meta["non-card-action-count"] > 3:
                raise Exception("3 action error")
            elif meta["non-card-action-count"] > 2 and "chilled" in player_data["status"] and player_data["status"]["chilled"] > 0:
                raise Exception("2 action error")
            if step["type"] == "movement":
                try:
                    return_string = self.handle_future_movement(game_state, player, step["name"], step["value"], platonic_step, return_string, turn_conf)
                except Exception as e:
                    error_msg = e.args[0]
                    if error_msg == "rooted_warning":
                        error_msg = ""
                        warning = "**You are rooted, so the movement effect of this card will probably not work!**"
                        turn_conf.append(warning)
                    elif error_msg == "wall move error":
                        error_msg = ""
                        warning = "\n**Warning**\n You probably won't move, since you're against a wall! "
                        turn_conf.append(warning)
                    else:
                        raise e
            if step["type"] == "regeneration":
                return_string = self.handle_future_regeneration(game_state, player, step["name"], step["value"],platonic_step, return_string, turn_conf)
            if step["type"] == "draw":
                return_string = return_string + "\n • " + platonic_step["verbose-text-future"].format(step["value"], "You")
        turn_conf.append(return_string)

    def handle_future_negate_damage(self, game_state, player_num, name, val, platonic, return_string, turn_conf, is_card=False):
        if is_card:
            player_status = game_state[player_num]["status"]
            if name in player_status:
                player_status[name] = player_status[name] + val
            else:
                player_status[name] = val
            return_string = return_string + "\n > • " + platonic["verbose-text-future"].format(val, "You")
        return return_string

    def handle_future_counter(self, game_state, player_num, name, val, platonic, return_string, turn_conf,
                                    is_card=False):
        if is_card:
            return_string = return_string + "\n > • " + platonic["verbose-text-future"].format(val, "You")
        return return_string

    def handle_future_buff(self, game_state, player_num, name, val, platonic, return_string, turn_conf,
                                    is_card=False):
        if is_card:
            player_status = game_state[player_num]["status"]
            if name in player_status:
                player_status[name] = player_status[name] + val
            else:
                player_status[name] = val
            return_string = return_string + "\n > • " + platonic["verbose-text-future"].format(val, "You")
        return return_string

    def handle_future_opponent_buff(self, game_state, player_num, name, val, platonic, return_string, turn_conf,
                                    is_card=False):
        if player_num == "p1":
            opp_num = "p2"
        else:
            opp_num = "p1"

        if is_card:
            player_status = game_state[opp_num]["status"]
            if name in player_status:
                player_status[name] = player_status[name] + val
            else:
                player_status[name] = val
        return return_string

    def handle_future_debuff(self, game_state, player_num, name, val, platonic, return_string, turn_conf,
                                    is_card=False):
        if player_num == "p1":
            opp_num = "p2"
        else:
            opp_num = "p1"

        if is_card:
            player_status = game_state[opp_num]["status"]
            if name in player_status:
                player_status[name] = player_status[name] + val
            else:
                player_status[name] = val
            return_string = return_string + "\n > • " + platonic["verbose-text-future"].format(val, "You")
        return return_string

    def handle_future_self_debuff(self, game_state, player_num, name, val, platonic, return_string, turn_conf,
                                    is_card=False):
        if is_card:
            player_status = game_state[player_num]["status"]
            if "self-" in name:
                name = name.replace("self-", "")
            if name in player_status:
                player_status[name] = player_status[name] + val
            else:
                player_status[name] = val
            return_string = return_string + "\n > • " + platonic["verbose-text-future"].format(val, "You")
        return return_string

    def handle_future_movement(self, game_state, player_num, name, val, platonic, return_string, turn_conf, is_card=False):
        if is_card:
            return_string = return_string + "\n > • " + platonic["verbose-text-future"].format(val, "You")
        else:
            return_string = return_string + "\n • " + platonic["verbose-text-future"].format(val, "You")
        if player_num == "p1":
            opp_num = "p2"
        else:
            opp_num = "p1"

        player_data = game_state[player_num]
        opp_data = game_state[opp_num]

        if "rooted" in player_data["status"] and player_data["status"]["rooted"] > 0:
            turn_conf.append(return_string)
            raise Exception("rooted_warning")
        left_adjacent = False
        right_adjacent = False
        if player_data["position"] > opp_data["position"]:
            if name =="forwards":
                name = "left"
            elif name == "backwards":
                name = "right"
            if player_data["position"] - opp_data["position"] == 1:
                left_adjacent = True
        elif player_data["position"] < opp_data["position"]:
            if name =="forwards":
                name = "right"
            elif name == "backwards":
                name = "left"
            if player_data["position"] - opp_data["position"] == -1:
                right_adjacent = True

        if name == "left":
            if player_data["position"] == 0:
                raise Exception("wall move error")
            if left_adjacent:
                if "interrupted" not in opp_data["status"]:
                    opp_data["status"]["interrupted"] = 1
                else:
                    opp_data["status"]["interrupted"] = opp_data["status"]["interrupted"] + 1
            else:
                player_data["position"] = player_data["position"] - val
        if name == "right":
            if player_data["position"] == 10:
                raise Exception("wall move error")
            if right_adjacent:
                if "interrupted" not in opp_data["status"]:
                    opp_data["status"]["interrupted"] = 1
                else:
                    opp_data["status"]["interrupted"] = opp_data["status"]["interrupted"] + 1
            else:
                player_data["position"] = player_data["position"] + val
        return return_string

    def handle_future_regeneration(self, game_state, player_num, name, val, platonic, return_string, turn_conf, is_card=False):
        player_data = game_state[player_num]
        player_data["mana"] = player_data["mana"] + val
        if is_card:
            return_string = return_string + "\n > • " + platonic["verbose-text-future"].format(val, "You")
        else:
            return_string = return_string + "\n • " + platonic["verbose-text-future"].format(val, "You")
        warning = "\n**Warning**\nMana doesn't carry over to the next turn, so use it or lose it!"
        turn_conf.append(warning)
        return return_string

    def handle_future_damage(self, game_state, player_num, name, val, platonic, return_string, turn_conf, is_card=False, self_dmg =False):
        if self_dmg:
            opp_num = player_num
        else:
            if player_num == "p1":
                opp_num = "p2"
            else:
                opp_num = "p1"

        if name == "damage-boost":
            card_played_counter = 0
            for step in game_state[player_num]["next-turn"]["steps"]:
                if "name" in step and step["name"] == "card":
                    card_played_counter = card_played_counter + 1
            val = card_played_counter * int(val)
        elif name == "damage-double-empower-consume":
            if "empower" in game_state[player_num]["status"]:
                val = (int(game_state[player_num]["status"]["empower"]) * 2) + int(val)
                game_state[player_num]["status"]["empower"] = 0
        elif name == "damage-minus-movement-actions":
            move_counter = 0
            for step in game_state[player_num]["next-turn"]["steps"]:
                if step["type"] == "movement":
                    move_counter = move_counter + 1

            val = int(val) - move_counter
            if val < 0:
                warning = "\n**Warning**\nYou won't deal any damage with this move!"
                turn_conf.append(warning)
                val = 0
        player_data = game_state[player_num]
        if not self_dmg:
            if "empower" in player_data["status"] and player_data["status"]["empower"] > 0:
                val = int(val) + 1
                player_data["status"]["empower"] = player_data["status"]["empower"] - 1
        opp_data = game_state[opp_num]

        opp_data["current-hp"] = int(opp_data["current-hp"]) - int(val)
        return_string = return_string + "\n > • " + platonic["verbose-text-future"].format(val, "You")
        if self_dmg:
            if opp_data["current-hp"] <= 0:
                warning = "\n**Warning**\nIt looks like using this move might kill you!"
                turn_conf.append(warning)
        return return_string

    def interpret_emoji_from_hand_reaction(self, hand, emoji):
        emoji_array = ["0⃣", "1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣", "🔟"]

        if emoji in ["🔵", "🔴", "⭐", "⬅️", "➡️"]:
            if emoji == "🔵":
                return {'type': "draw", "name": "draw-options", "value": 1}
            if emoji == "🔴":
                return {'type': "draw", "name": "draw-pressure", "value": 1}
            if emoji == "➡️":
                return {'type': "movement", "name": "right", "value": 1}
            if emoji == "⬅️":
                return {'type': "movement", "name": "left", "value":  1}
            if emoji == "⭐":
                return {'type': "regeneration", "name": "meditate", "value":  1}
        for z in range(0, len(hand)):
            if emoji == emoji_array[z]:
                return {'type': "play", "name": "card", "value":  z, "sub-steps": hand[z]["effects"]}

    async def update_based_on_hand_embed_button_press(self, discord_client, db, hand_msg_id, channel, ch_id, metadata_map, emoji):

        ref = db.collection(u'fg-fights').document("{0}".format(str(metadata_map["fight-id"])))
        doc = ref.get()
        if doc.exists:
            # make sure not to write back the wonky predictive state to db, we're only going to write back the steps
            fight_data = doc.to_dict()
            next_turn = fight_data[metadata_map["player"]]["next-turn"]
            if next_turn["submitted"]:
                await channel.send("You've already submitted your turn! Please wait until your opponent plays.")
                return
            turn_conf_text = []
            hand = fight_data[metadata_map["player"]]["hand"]
            temp_cards = []
            # iterate through and remove the used cards
            for step in next_turn["steps"]:
                if step and step["name"] == "card":
                    temp_cards.append(hand.pop(step["value"]))
            # create step out of action or card data; play (subtract mana and remove card and increment play counter), movement, regen, block, shatter, damage, inflict, buff, late_movement, draw
            card_step = self.interpret_emoji_from_hand_reaction(hand, emoji)
            next_turn["steps"].append(card_step)

            error_msg = ""
            warning = ""
            turn_meta = {"non-card-action-count" : 0,
                         "temp-cards": temp_cards}
            for step in next_turn["steps"]:
                try:
                    if step:
                        self.predict_game_state_for_solo_stack_step(db, step, fight_data,
                                                                           metadata_map["player"], turn_meta, turn_conf_text)
                    else:
                        error_msg = "\n**ERROR**\nYour selection couldn't be found! Did you select a valid card?"
                        turn_conf_text.append(error_msg)
                except Exception as e:
                    error_msg = e.args[0]
                    print(error_msg)
                    if error_msg == "3 action error":
                        turn_conf_text.append("\n**ERROR**\nYou reached your 3 non-card action limit! You can only play cards - "
                                              "you'll have to clear your turn plan!")
                    if error_msg == "2 action error":
                        error_msg = ""
                        turn_conf_text.append("\n**Warning**\nYou are chilled and can only take 2 non-card actions! This action will fail!")

                    elif error_msg == "mana_warning":
                        error_msg = ""
                        warning = "\n**Warning**\nYou don't have enough mana to play this card, so you're wagering that this card will be discounted by previous actions!\n " \
                                  "*🟦 Options cards are discounted when your opponent plays a card;\n" \
                                  "🟥 Pressure cards are discounted when you play an options cards. \n" \
                                  "(Pressure discounts are already accounted for in this plan)*"
                        turn_conf_text.append(warning)
                    elif error_msg == "range_warning":
                        error_msg = ""
                        warning = "\n**Warning**\nBased on your current position, you will be out of range of your opponent for this card.\n" \
                                  "*Damage and debuffs will not be applied to your opponent if they are out of range.*"

                        turn_conf_text.append(warning)

                    # other errors might include being rooted and trying to move (without a card), or trying to play option while off-balance, or drawing more than 10 cards.
                    elif "recognized. Please contact" in error_msg:
                        turn_conf_text.append(error_msg)
                    else:
                        raise e

            if error_msg == "":
                # we're submitting JUST the steps to the db
                ref.update({"{0}".format(db.field_path(metadata_map["player"], "next-turn", "steps")): next_turn["steps"]})
                if card_step and card_step["name"] == "card":
                    hand.pop(card_step["value"])

            message = await channel.fetch_message(metadata_map["turn-confirmation-message-id"])
            desc = "{0}".format("\n".join(turn_conf_text))
            if len(desc) >= 2040:
                desc = desc[-2040:]
            embed = discord.Embed(title="Next Turn Plan \n({0} mana / {1} non-card actions left)\nEnd at position: {2}"
                                  .format(fight_data[metadata_map["player"]]["mana"],
                                          str(3 - turn_meta["non-card-action-count"]),
                                          fight_data[metadata_map["player"]]["position"] + 1), colour=discord.Colour(0xd0021b),
                                  description=desc,
                                  timestamp=datetime.datetime.now().astimezone(timezone('US/Pacific')))
            await message.edit(embed=embed)

            channel = await discord_client.fetch_channel(ch_id)
            h_message = await channel.fetch_message(hand_msg_id)
            hand_embed = self.create_hand_embed(fight_data, metadata_map["player"])
            await h_message.edit(embed=hand_embed)
            # edit the embed of the discord message, overwriting the entirety of it with our new iteration of the stack

    async def render_turn_submitted_success(self, discord_client, db, fight_data, fight_id, player):
        if player == "p1":
            opp_num = "p2"
            opponent_data = fight_data["p2"]
        else:
            opp_num = "p1"
            opponent_data = fight_data["p1"]
        player_data = fight_data[player]
        if len(player_data["next-turn"]["steps"]) == 0:
            channel_id = fight_data["metadata"][player]["channel"]
            ch_obj = await discord_client.fetch_channel(channel_id)
            await ch_obj.send("Submit Failed! Your turn is empty!")
            return
        # update log to say user submitted turn
        submit_entry = "{0} {1} has submitted their turn!\n".format(player_data["player"]["name"], player_data["player"]["emoji"])
        player_data["next-turn"]["submitted"] = True
        fight_data["logs"].append(submit_entry)

        # check if both turns-submitted = true and reveal != -1 for both players
        if opponent_data["next-turn"]["submitted"]:

            # If so, update_fight_date_based_on_both, resolving the stack and modifying game state
            game_over = await self.update_fight_data_based_on_both_turns_submitted(db, discord_client, fight_data, fight_id)
            if game_over:
                return
            hand_update = None
            opp_num = None
        else:
            # If not, change hands to success message
            hand_update = {player: discord.Embed(title="Your Actions", colour=discord.Colour(0xd0021b),
                                  description="Successfully submitted turn! Waiting on your opponent...",
                                  timestamp=datetime.datetime.now().astimezone(timezone('US/Pacific')))}
        # update the game state in db
        ref = db.collection(u'fg-fights').document(str(fight_id))
        ref.update(fight_data)

        # Either way, rerender the fight - either to update the game state or update log/last updated
        await self.update_render_entire_fight_from_fight_metadata(discord_client, fight_data, hand_update, opp_num)

        return


    async def update_fight_data_based_on_both_turns_submitted(self, db, discord_client, fight_data, fight_id):
        try:
            p1_steps = fight_data["p1"]["next-turn"]["steps"]
            p2_steps = fight_data["p2"]["next-turn"]["steps"]
            longer_steps = max([len(p1_steps), len(p2_steps)])
            meta = {"p1-non-card-action-count": 0 , "p2-non-card-action-count": 0, 'p1-card-count': 0, 'p2-card-count': 0}
            for z in range(0, longer_steps):
                fight_data["p1"]["status"].pop("perfect-negate-damage", None)
                fight_data["p2"]["status"].pop("perfect-negate-damage", None)
                fight_data["p1"]["status"].pop("perfect-block-draw", None)
                fight_data["p2"]["status"].pop("perfect-block-draw", None)
                fight_data["p1"]["status"].pop("perfect-negate-damage-impale", None)
                fight_data["p2"]["status"].pop("perfect-negate-damage-impale", None)

                if z >= len(p1_steps):
                    p2_step = p2_steps[z]
                    p1_step = None
                elif z >= len(p2_steps):
                    p1_step = p1_steps[z]
                    p2_step = None
                else:
                    p1_step = p1_steps[z]
                    p2_step = p2_steps[z]
                # resolve the stack while updating players hp, position, mana and hands
                self.resolve_game_state_for_stack(db, p1_step, p2_step, fight_data, meta)

                # for both players check for hp <= 0
                if await self.check_for_end_game_and_update_active_fights(db, discord_client, fight_data, fight_id):
                    return True
                fight_data["logs"].append("\n\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_")
            # update the battle log, including the revealed cards and noting that statuses wear off
            fight_data["p1"]["status"].pop("negate-damage", None)
            fight_data["p2"]["status"].pop("negate-damage", None)
            fight_data["p1"]["status"].pop("perfect-negate-damage", None)
            fight_data["p2"]["status"].pop("perfect-negate-damage", None)
            fight_data["p1"]["status"].pop("perfect-negate-damage-impale", None)
            fight_data["p2"]["status"].pop("perfect-negate-damage-impale", None)
            fight_data["p1"]["status"].pop("perfect-block-draw", None)
            fight_data["p2"]["status"].pop("perfect-block-draw", None)
            fight_data["p1"]["status"].pop("interrupted", None)
            fight_data["p2"]["status"].pop("interrupted", None)
            fight_data["p1"]["status"].pop("immune-to-damage", None)
            fight_data["p2"]["status"].pop("immune-to-damage", None)
            fight_data["p1"]["status"].pop("impale-on-move-this-round", None)
            fight_data["p2"]["status"].pop("impale-on-move-this-round", None)
            carry_over_statuses = ["empower", "range-buff-2", "next-card-shatter", "next-card-range-increase-2", "impale"]
            for status in fight_data["p1"]["status"]:
                if status not in carry_over_statuses:
                    if type(fight_data["p1"]["status"][status]) is dict and "turns-left" in fight_data["p1"]["status"][status]:
                        fight_data["p1"]["status"][status]["turns-left"] = fight_data["p1"]["status"][status]["turns-left"] - 1
                    else:
                        if int(fight_data["p1"]["status"][status]) > 0:
                            fight_data["p1"]["status"][status] = int(fight_data["p1"]["status"][status]) - 1

            for status in fight_data["p2"]["status"]:
                if status not in carry_over_statuses:
                    if type(fight_data["p2"]["status"][status]) is dict and "turns-left" in fight_data["p2"]["status"][status]:
                        fight_data["p2"]["status"][status]["turns-left"] = fight_data["p2"]["status"][status]["turns-left"] - 1
                    else:
                        if int(fight_data["p2"]["status"][status]) > 0:
                            fight_data["p2"]["status"][status] = int(fight_data["p2"]["status"][status]) - 1

            # if status = 0?
            # end of turn status
            if "teleport-to-position" in fight_data["p1"]["status"] and fight_data["p1"]["status"]["teleport-to-position"]["turns-left"] <= 0:
                pre_teleport_pos = fight_data["p1"]["position"]
                fight_data["p1"]["position"] = fight_data["p1"]["status"]["teleport-to-position"]["position"]
                if fight_data["p1"]["position"] == fight_data["p2"]["position"]:
                    if fight_data["p2"]["position"] - pre_teleport_pos > 0:
                        fight_data["p1"]["position"] = fight_data["p2"]["position"] - 1
                    else:
                        fight_data["p1"]["position"] = fight_data["p2"]["position"] + 1
                if "impale-on-move-this-round" in fight_data["p1"]["status"]:
                    if "impale" in fight_data["p1"]["status"]:
                        fight_data["p1"]["status"]["impale"] = fight_data["p1"]["status"]["impale"] + fight_data["p1"]["status"]["impale-on-move-this-round"]
                    else:
                        fight_data["p1"]["status"]["impale"] = fight_data["p1"]["status"]["impale-on-move-this-round"]
                    fight_data["logs"].append("{0} gained {1} stacks of impale for moving!"
                                              .format(fight_data["p1"]["player"]["name"],
                                                      fight_data["p1"]["status"]["impale-on-move-this-round"]))

                fight_data["logs"].append("{0} was teleported back to {1} as a result of a prior blink effect!".format(fight_data["p1"]["player"]["name"], fight_data["p1"]["position"]))
                fight_data["p1"]["status"].pop("teleport-to-position", None)

            if "teleport-to-position" in fight_data["p2"]["status"] and fight_data["p2"]["status"]["teleport-to-position"]["turns-left"] <= 0:
                pre_teleport_pos = fight_data["p2"]["position"]
                fight_data["p2"]["position"] = fight_data["p2"]["status"]["teleport-to-position"]["position"]
                if fight_data["p1"]["position"] == fight_data["p2"]["position"]:
                    if fight_data["p1"]["position"] - pre_teleport_pos > 0:
                        fight_data["p2"]["position"] = fight_data["p1"]["position"] - 1
                    else:
                        fight_data["p2"]["position"] = fight_data["p1"]["position"] + 1
                if "impale-on-move-this-round" in fight_data["p2"]["status"]:
                    if "impale" in fight_data["p2"]["status"]:
                        fight_data["p2"]["status"]["impale"] = fight_data["p2"]["status"]["impale"] + fight_data["p2"]["status"]["impale-on-move-this-round"]
                    else:
                        fight_data["p2"]["status"]["impale"] = fight_data["p2"]["status"]["impale-on-move-this-round"]
                    fight_data["logs"].append("{0} gained {1} stacks of impale for moving!"
                                              .format(fight_data["p2"]["player"]["name"],
                                                      fight_data["p2"]["status"]["impale-on-move-this-round"]))

                fight_data["logs"].append("{0} was teleported back to {1} as a result of a prior blink effect!".format(fight_data["p2"]["player"]["name"], fight_data["p2"]["position"]))
                fight_data["p2"]["status"].pop("teleport-to-position", None)

            # to get range buff next turn, just check for any value for the next card range increase buff, turn it to zero and transfer it to a coherent status
            if "next-card-range-increase-2" in fight_data["p1"]["status"] and fight_data["p1"]["status"]["next-card-range-increase-2"] > 0:

                fight_data["p1"]["status"]["range-buff-2"] = {"next-cards": fight_data["p1"]["status"]["next-card-range-increase-2"],
                                                            "range": 2}
                fight_data["p1"]["status"].pop("next-card-range-increase-2", None)
                fight_data["logs"].append("{0}'s next {1} damage dealing cards have +{2} range!".format(fight_data["p1"]["player"]["name"], fight_data["p1"]["status"]["range-buff-2"]["next-cards"], fight_data["p1"]["status"]["range-buff-2"]["range"]))

            if "next-card-range-increase-2" in fight_data["p2"]["status"] and fight_data["p2"]["status"]["next-card-range-increase-2"] > 0:

                fight_data["p2"]["status"]["range-buff-2"] = {
                    "next-cards": fight_data["p2"]["status"]["next-card-range-increase-2"],
                    "range": 2}
                fight_data["p2"]["status"].pop("next-card-range-increase-2", None)
                fight_data["logs"].append("{0}'s next {1} damage dealing cards have +{2} range!".format(fight_data["p2"]["player"]["name"], fight_data["p2"]["status"]["range-buff-2"]["next-cards"], fight_data["p2"]["status"]["range-buff-2"]["range"]))


            # increment round
            fight_data["round"] = fight_data["round"] + 1
            fight_data["logs"].append("---------- **Round {0}** ---------\n".format(fight_data["round"]))
            p1_channel_id = fight_data["metadata"]["p1"]["channel"]
            ch_obj = await discord_client.fetch_channel(p1_channel_id)
            await ch_obj.send("Round {0} Start!".format(fight_data["round"]))

            p2_channel_id = fight_data["metadata"]["p2"]["channel"]
            ch_obj = await discord_client.fetch_channel(p2_channel_id)
            await ch_obj.send("Round {0} Start!".format(fight_data["round"]))

            # for both players reset mana
            fight_data["p1"]["mana"] = fight_data["round"]
            fight_data["p2"]["mana"] = fight_data["round"]

            # for both players, iterate through cards in hand and set submitted to false



            # for both players, set actions-submitted and submitted to false, set reveal to -1 and clear steps map
            empty_next = {
                u'actions-submitted': False,
                u'reveal': -1,
                u'steps': [],
                u'submitted': False
            }
            fight_data["p1"]["next-turn"] = empty_next
            fight_data["p2"]["next-turn"] = empty_next

        except Exception as e:
            print(e)
            raise e
            #logging.error(e)

    def resolve_game_state_for_stack(self, db, p1_step, p2_step, game_state, meta):
        sub_stack_type_order = [{"movement": self.handle_movement}, {"regeneration": self.handle_regeneration},
                     {"negate-damage": self.handle_negate_damage}, {"counter":self.handle_counter}, {"damage": self.handle_damage},
                     {"self-damage": self.handle_self_damage},
                     {"self-debuff":self.handle_self_debuff}, {"debuff": self.handle_debuff},
                     {"buff":self.handle_buff}, {"opponent-buff":self.handle_opponent_buff},
                     {"late-movement":self.handle_late_movement}, {"draw": self.handle_draw}]
        player1_data = game_state["p1"]
        hand1 = player1_data["hand"]
        player2_data = game_state["p2"]
        hand2 = player2_data["hand"]

        p1_resolver = {}
        p2_resolver = {}
        p1_card = False
        p2_card = False
        # look up verbose-text-future from fg-log-steps table based on card
        if p1_step:
            p1_step_doc = db.collection(u'fg-log-steps').document(p1_step["name"]).get()
            if not p1_step_doc.exists:
                raise Exception(
                    "Step `{0}` was not recognized. Please contact <@116045478709297152>, this is a bug.".format(
                        p1_step["name"]))

            p1_platonic_step = p1_step_doc.to_dict()
            p1_resolver = self.construct_step_resolver(db, game_state, player1_data, p1_step, p1_platonic_step, hand1,
                                                       meta)
            p1_card = p1_step["name"] == "card"
        if p2_step:
            p2_step_doc = db.collection(u'fg-log-steps').document(p2_step["name"]).get()

            if not p2_step_doc.exists:
                raise Exception(
                    "Step `{0}` was not recognized. Please contact <@116045478709297152>, this is a bug.".format(
                        p2_step["name"]))

            # reminder to handle range , discounts

            p2_platonic_step = p2_step_doc.to_dict()

            p2_resolver = self.construct_step_resolver(db, game_state, player2_data, p2_step, p2_platonic_step, hand2, meta)
            p2_card = p2_step["name"] == "card"

        for resolver_type in sub_stack_type_order:
            res_string = list(resolver_type)[0]
            if res_string in p1_resolver and res_string in p2_resolver:
                # CLASH
                resolver_type[res_string](game_state, p1_resolver[res_string], p2_resolver[res_string], p1_card, p2_card, meta)
            else:
                if res_string in p1_resolver:
                    resolver_type[res_string](game_state, p1_resolver[res_string], [], p1_card, False, meta)
                if res_string in p2_resolver:
                    resolver_type[res_string](game_state, [], p2_resolver[res_string], False, p2_card, meta)

        # handle end-of-action special statuses like perfect block draw
        if "immune-to-damage" in player1_data["status"] and player1_data["status"]["immune-to-damage"] > 0:
            player1_data["current-hp"] = player1_data["status"]["immune-to-damage"]
        if "immune-to-damage" in player2_data["status"] and player2_data["status"]["immune-to-damage"] > 0:
            player2_data["current-hp"] = player2_data["status"]["immune-to-damage"]

        if "perfect-block-draw" in player1_data["status"] and player1_data["status"]["perfect-block-draw"] > 0:
            try:
                self.draw_cards_from_deck(player1_data["hand"], player1_data["pressure-deck"],
                                                  player1_data["status"]["perfect-block-draw"], game_state["p1"]["discard"] , "pressure")

                game_state["logs"].append("{0} drew a pressure card as a result of a perfect block!\n".format(player1_data["player"]["name"]))
            except Exception as e:
                game_state["logs"].append(
                    "{0} attempted to draw a pressure card as a result of a perfect block, but {1}\n".format(player1_data["player"]["name"], e.args[0]))
            player1_data["status"]["perfect-block-draw"] = 0


        if "perfect-block-draw" in player2_data["status"] and player2_data["status"]["perfect-block-draw"] > 0:
            try:
                self.draw_cards_from_deck(player2_data["hand"], player2_data["pressure-deck"],
                                      player2_data["status"]["perfect-block-draw"], game_state["p2"]["discard"],
                                      "pressure")

                game_state["logs"].append(
                    "{0} drew a pressure card as a result of a perfect block!\n".format(player2_data["player"]["name"]))
            except Exception as e:
                game_state["logs"].append(
                    "{0} attempted to draw a pressure card as a result of a perfect block, but {1}\n".format(player2_data["player"]["name"], e.args[0]))
            player2_data["status"]["perfect-block-draw"] = 0

        # discount opponents options
        if p1_card:
            meta["p1-card-count"] = meta["p1-card-count"] + 1
            for card in game_state["p2"]["hand"]:
                if card["deck"] == "options" and card["current-mana"] > 1:
                    card["current-mana"] = card["current-mana"] - 1
        else:
            meta["p1-non-card-action-count"] = meta["p1-non-card-action-count"] + 1
        if p2_card:
            meta["p2-card-count"] = meta["p2-card-count"] + 1
            for card in game_state["p1"]["hand"]:
                if card["deck"] == "options" and card["current-mana"] > 1:
                    card["current-mana"] = card["current-mana"] - 1

        else:
            meta["p2-non-card-action-count"] = meta["p2-non-card-action-count"] + 1
    def handle_movement(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):
        if p1_resolver_l and p2_resolver_l:
            for p1_resolver in p1_resolver_l:
                for p2_resolver in p2_resolver_l:
                    spaces = max(int(p1_resolver["value"]),  int(p2_resolver["value"]))
                    if "summon" in p1_resolver["name"]:
                        if "inflict" in p1_resolver["name"]:
                            if game_state["p1"]["position"] > game_state["p2"]["position"]:
                                forward_pos = (game_state["p1"]["position"] - 1) - game_state["p2"]["position"]
                            else:
                                forward_pos = game_state["p2"]["position"] - (game_state["p1"]["position"] + 1)
                            p1_resolver["name"] = "forwards"
                            self.handle_solo_teleport(game_state, forward_pos, game_state["p2"],
                                                      game_state["p1"],
                                                      p1_resolver)
                    if "teleport" in p1_resolver["name"]:
                        if "inflict" in p1_resolver["name"]:
                            if "forwards" in p1_resolver["name"]:
                                p1_resolver["name"] = "forwards"
                            elif "backwards" in p1_resolver["name"]:
                                p1_resolver["name"] = "backwards"
                            self.handle_solo_teleport(game_state, p1_resolver["value"], game_state["p2"],
                                                      game_state["p1"],
                                                      p1_resolver)
                        elif "self" in p1_resolver["name"]:
                            if "forwards" in p1_resolver["name"]:
                                p1_resolver["name"] = "forwards"
                            elif "backwards" in p1_resolver["name"]:
                                p1_resolver["name"] = "backwards"
                            self.handle_solo_teleport(game_state, p1_resolver["value"], game_state["p1"], game_state["p2"],
                                                      p1_resolver)
                    if "summon" in p2_resolver["name"]:
                        if "inflict" in p2_resolver["name"]:
                            if game_state["p2"]["position"] > game_state["p1"]["position"]:
                                forward_pos = (game_state["p2"]["position"] - 1) - game_state["p1"]["position"]
                            else:
                                forward_pos = game_state["p1"]["position"] - (game_state["p2"]["position"] + 1)
                            p2_resolver["name"] = "forwards"
                            self.handle_solo_teleport(game_state, forward_pos, game_state["p1"],
                                                      game_state["p2"],
                                                      p2_resolver)
                    if "teleport" in p2_resolver["name"]:
                        if "inflict" in p2_resolver["name"]:
                            if "forwards" in p2_resolver["name"]:
                                p2_resolver["name"] = "forwards"
                            elif "backwards" in p2_resolver["name"]:
                                p2_resolver["name"] = "backwards"
                            self.handle_solo_teleport(game_state, p2_resolver["value"], game_state["p1"], game_state["p2"],
                                                          p2_resolver)
                        elif "self" in p2_resolver["name"]:
                            if "forwards" in p2_resolver["name"]:
                                p2_resolver["name"] = "forwards"
                            elif "backwards" in p2_resolver["name"]:
                                p2_resolver["name"] = "backwards"
                            self.handle_solo_teleport(game_state, p2_resolver["value"], game_state["p2"], game_state["p1"],
                                                          p2_resolver)

                    for x in range(0, spaces):
                        p1_pos = game_state["p1"]["position"]
                        p2_pos = game_state["p2"]["position"]
                        if p1_resolver["value"] == 0:
                            self.handle_solo_movement(game_state, 1, game_state["p2"], game_state["p1"], p2_resolver, is_card_p2, meta["p2-non-card-action-count"])
                            p2_resolver["value"] = p2_resolver["value"] - 1
                        elif p2_resolver["value"] == 0:
                            self.handle_solo_movement(game_state, 1, game_state["p1"], game_state["p2"], p1_resolver, is_card_p1, meta["p1-non-card-action-count"])
                            p1_resolver["value"] = p1_resolver["value"] - 1
                        else:
                            self.handle_solo_movement(game_state, 1, game_state["p2"], game_state["p1"], p2_resolver, is_card_p2, meta["p2-non-card-action-count"])
                            self.handle_solo_movement(game_state, 1, game_state["p1"], game_state["p2"], p1_resolver, is_card_p1, meta["p1-non-card-action-count"])
                            p1_resolver["value"] = p1_resolver["value"] - 1
                            p2_resolver["value"] = p2_resolver["value"] - 1
                        if game_state["p1"]["position"] == game_state["p2"]["position"]:
                            if p2_pos - p1_pos > 0:
                                if game_state["p1"]["position"] > 4:
                                    game_state["p1"]["position"] = p1_pos
                                if game_state["p2"]["position"] < 6:
                                    game_state["p2"]["position"] = p2_pos
                            else:
                                if game_state["p1"]["position"] < 4:
                                    game_state["p1"]["position"] = p1_pos
                                if game_state["p2"]["position"] > 6:
                                    game_state["p2"]["position"] = p2_pos

        else:
            if p1_resolver_l:
                for p1_resolver in p1_resolver_l:
                    if "summon" in p1_resolver["name"]:
                        if "inflict" in p1_resolver["name"]:
                            if game_state["p1"]["position"] > game_state["p2"]["position"]:
                                forward_pos = (game_state["p1"]["position"] - 1) - game_state["p2"]["position"]
                            else:
                                forward_pos = game_state["p2"]["position"] - (game_state["p1"]["position"] + 1)
                            p1_resolver["name"] = "forwards"
                            self.handle_solo_teleport(game_state, forward_pos, game_state["p2"],
                                                      game_state["p1"],
                                                      p1_resolver)
                    if "teleport" in p1_resolver["name"]:
                        if "inflict" in p1_resolver["name"]:
                            if "forwards" in p1_resolver["name"]:
                                p1_resolver["name"] = "forwards"
                            elif "backwards" in p1_resolver["name"]:
                                p1_resolver["name"] = "backwards"
                            self.handle_solo_teleport(game_state, p1_resolver["value"], game_state["p2"],
                                                      game_state["p1"],
                                                      p1_resolver, is_card_p1, meta[""])
                        elif "self" in p1_resolver["name"]:
                            if "forwards" in p1_resolver["name"]:
                                p1_resolver["name"] = "forwards"
                            elif "backwards" in p1_resolver["name"]:
                                p1_resolver["name"] = "backwards"
                            self.handle_solo_teleport(game_state, p1_resolver["value"], game_state["p1"], game_state["p2"],
                                                      p1_resolver)
                    else:
                        for x in range(0, int(p1_resolver["value"])):
                            self.handle_solo_movement(game_state, 1, game_state["p1"], game_state["p2"], p1_resolver, is_card_p1, meta["p1-non-card-action-count"])
            if p2_resolver_l:
                for p2_resolver in p2_resolver_l:
                    if "summon" in p2_resolver["name"]:
                        if "inflict" in p2_resolver["name"]:
                            if game_state["p2"]["position"] > game_state["p1"]["position"]:
                                forward_pos = (game_state["p2"]["position"] - 1) - game_state["p1"]["position"]
                            else:
                                forward_pos = game_state["p1"]["position"] - (game_state["p2"]["position"] + 1)
                            p2_resolver["name"] = "forwards"
                            self.handle_solo_teleport(game_state, forward_pos, game_state["p1"],
                                                      game_state["p2"],
                                                      p2_resolver)
                    if "teleport" in p2_resolver["name"]:
                        if "inflict" in p2_resolver["name"]:
                            if "forwards" in p2_resolver["name"]:
                                p2_resolver["name"] = "forwards"
                            elif "backwards" in p2_resolver["name"]:
                                p2_resolver["name"] = "backwards"
                            self.handle_solo_teleport(game_state, p2_resolver["value"], game_state["p1"],
                                                      game_state["p2"],
                                                      p2_resolver)
                        elif "self" in p2_resolver["name"]:
                            if "forwards" in p2_resolver["name"]:
                                p2_resolver["name"] = "forwards"
                            elif "backwards" in p2_resolver["name"]:
                                p2_resolver["name"] = "backwards"
                            self.handle_solo_teleport(game_state, p2_resolver["value"], game_state["p2"],
                                                      game_state["p1"],
                                                      p2_resolver)
                    else:
                        for x in range(0, int(p2_resolver["value"])):
                            self.handle_solo_movement(game_state, 1, game_state["p2"], game_state["p1"], p2_resolver, is_card_p2, meta["p2-non-card-action-count"])


    def handle_solo_teleport(self, game_state, val, player_data, opp_data, resolver, is_card=True, non_card_count=0):
        # non card count is zero when its a card, since its irrelevant
        if "chilled" in player_data["status"] and player_data["status"]["chilled"] and non_card_count >= 2 and not is_card:
            game_state["logs"].append(resolver["verbose-text-failed"]
                                      .format(player_data["player"]["name"], val,
                                              " was chilled!"))
            return
        # check pre-reqs
        if "rooted" in player_data["status"] and player_data["status"]["rooted"] > 0:
            game_state["logs"].append(resolver["verbose-text-failed"]
                                      .format(player_data["player"]["name"], val,
                                              " was rooted in place!"))
            return
        if "impale-on-move-this-round" in player_data["status"]:
            if "impale" in player_data["status"]:
                player_data["status"]["impale"] = player_data["status"]["impale"] + player_data["status"]["impale-on-move-this-round"]
            else:
                player_data["status"]["impale"] = player_data["status"]["impale-on-move-this-round"]
            game_state["logs"].append("{0} gained {1} stacks of impale for moving!"
                                      .format(player_data["player"]["name"], player_data["status"]["impale-on-move-this-round"]))
        name = resolver["name"]
        left_adjacent = False
        right_adjacent = False
        if player_data["position"] > opp_data["position"]:
            if name == "forwards":
                name = "left"
            elif name == "backwards":
                name = "right"
            if player_data["position"] - opp_data["position"] == 1:
                left_adjacent = True
        elif player_data["position"] < opp_data["position"]:
            if name == "forwards":
                name = "right"
            elif name == "backwards":
                name = "left"
            if player_data["position"] - opp_data["position"] == -1:
                right_adjacent = True

        if name == "left":
            player_data["position"] = player_data["position"] - val
            thing_printed = False
            if player_data["position"] < 0:
                game_state["logs"].append(resolver["verbose-text-failed"]
                                          .format(player_data["player"]["name"], resolver["value"],
                                                  " instead teleported next to the left wall!"))
                thing_printed = True
                player_data["position"] = 0
            if player_data["position"] == opp_data["position"]:
                player_data["position"] = opp_data["position"] + 1
                if not thing_printed:
                    game_state["logs"].append(resolver["verbose-text-failed"]
                                              .format(player_data["player"]["name"], resolver["value"],
                                                      " instead teleported next to their opponent!"))
                return
            game_state["logs"].append(resolver["verbose-text-past"]
                                      .format(player_data["player"]["name"], str(val)))
        if name == "right":

            player_data["position"] = player_data["position"] + val
            thing_printed = False
            if player_data["position"] > 10:
                game_state["logs"].append(resolver["verbose-text-failed"]
                                          .format(player_data["player"]["name"], resolver["value"],
                                                  " instead teleported next to the right wall!"))
                player_data["position"] = 10
                thing_printed = True
            if player_data["position"] == opp_data["position"]:
                player_data["position"] = opp_data["position"] - 1
                if not thing_printed:
                    game_state["logs"].append(resolver["verbose-text-failed"]
                                              .format(player_data["player"]["name"], resolver["value"],
                                                      " instead teleported next to their opponent!"))
                return
            if not thing_printed:
                game_state["logs"].append(resolver["verbose-text-past"]
                                          .format(player_data["player"]["name"], val))
        return

    def handle_solo_movement(self, game_state, val, player_data, opp_data, resolver, is_card=True, non_card_count=0):
        # non card count is zero when its a card, since its irrelevant
        if "chilled" in player_data["status"] and player_data["status"]["chilled"] and non_card_count >= 2 and not is_card:
            game_state["logs"].append(resolver["verbose-text-failed"]
                                      .format(player_data["player"]["name"], val,
                                              " was chilled!"))
            return
        # check pre-reqs
        if "rooted" in player_data["status"] and player_data["status"]["rooted"] > 0:
            game_state["logs"].append(resolver["verbose-text-failed"]
                                      .format(player_data["player"]["name"], val,
                                              " was rooted in place!"))
            return
        if "impale-on-move-this-round" in player_data["status"]:
            if "impale" in player_data["status"]:
                player_data["status"]["impale"] = player_data["status"]["impale"] + player_data["status"]["impale-on-move-this-round"]
            else:
                player_data["status"]["impale"] = player_data["status"]["impale-on-move-this-round"]
            game_state["logs"].append("{0} gained {1} stacks of impale for moving!"
                                      .format(player_data["player"]["name"], player_data["status"]["impale-on-move-this-round"]))
        name = resolver["name"]
        left_adjacent = False
        right_adjacent = False
        if player_data["position"] > opp_data["position"]:
            if name == "forwards":
                name = "left"
            elif name == "backwards":
                name = "right"
            if player_data["position"] - opp_data["position"] == 1:
                left_adjacent = True
        elif player_data["position"] < opp_data["position"]:
            if name == "forwards":
                name = "right"
            elif name == "backwards":
                name = "left"
            if player_data["position"] - opp_data["position"] == -1:
                right_adjacent = True

        if name == "left":
            if player_data["position"] == 0:
                game_state["logs"].append(resolver["verbose-text-failed"]
                                          .format(player_data["player"]["name"], resolver["value"],
                                                  " but hit a wall!"))
                return
            if left_adjacent:

                if opp_data["position"] + val > 0:
                    opp_data["position"] = opp_data["position"] - val
                else:
                    opp_data["position"] = 0
                player_data["position"] = opp_data["position"] + 1
                game_state["logs"].append(resolver["verbose-text-past"]
                                          .format(player_data["player"]["name"],
                                                  str(val) + " step and also pushed the opponent 1"))
                return

            if left_adjacent and player_data["position"] == 1:
                if "interrupted" not in opp_data["status"]:
                    opp_data["status"]["interrupted"] = 1
                else:
                    opp_data["status"]["interrupted"] = opp_data["status"]["interrupted"] + 1
                game_state["logs"].append(resolver["verbose-text-failed"]
                                          .format(player_data["player"]["name"], val,
                                                  " but shoved the opponent into the wall instead! The opponent is interrupted!"))
                return
            else:
                player_data["position"] = player_data["position"] - val
                game_state["logs"].append(resolver["verbose-text-past"]
                                          .format(player_data["player"]["name"], str(val)))
        if name == "right":
            if player_data["position"] == 10:
                game_state["logs"].append(resolver["verbose-text-failed"]
                                          .format(player_data["player"]["name"], resolver["value"],
                                                  " but hit a wall!"))
                return
            if right_adjacent:
                if opp_data["position"] + val < 10:
                    opp_data["position"] = opp_data["position"] + val
                else:
                    opp_data["position"] = 10
                player_data["position"] = opp_data["position"] - 1
                game_state["logs"].append(resolver["verbose-text-past"]
                                          .format(player_data["player"]["name"],
                                                  str(val) + " step and also pushed the opponent 1"))
                return
            if right_adjacent and player_data["position"] == 9:
                if "interrupted" not in opp_data["status"]:
                    opp_data["status"]["interrupted"] = 1

                else:
                    opp_data["status"]["interrupted"] = opp_data["status"]["interrupted"] + 1
                game_state["logs"].append(resolver["verbose-text-failed"]
                                          .format(player_data["player"]["name"], val,
                                                  " but shoved the opponent into the wall instead! The opponent is interrupted!"))
                return
            else:
                player_data["position"] = player_data["position"] + val

                game_state["logs"].append(resolver["verbose-text-past"]
                                          .format(player_data["player"]["name"], val))
        return

    def handle_regeneration(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):
        if p1_resolver_l:
            for p1_resolver in p1_resolver_l:
                if  "chilled" in game_state["p1"]["status"] and game_state["p1"]["status"]["chilled"] and meta["p1-non-card-action-count"] >= 2 and not is_card_p1:
                    game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                              .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                      " was chilled!"))
                    continue
                game_state["p1"]["mana"] =  game_state["p1"]["mana"] + p1_resolver["value"]
                game_state["logs"].append(p1_resolver["verbose-text-past"]
                                          .format(game_state["p1"]["player"]["name"], p1_resolver["value"]))
        if p2_resolver_l:
            for p2_resolver in p2_resolver_l:
                if "chilled" in game_state["p2"]["status"] and game_state["p2"]["status"]["chilled"] and meta["p2-non-card-action-count"] >= 2 and not is_card_p2:
                    game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                              .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                      " was chilled!"))
                    continue
                game_state["p2"]["mana"] = game_state["p2"]["mana"] + p2_resolver["value"]
                game_state["logs"].append(p2_resolver["verbose-text-past"]
                                          .format(game_state["p2"]["player"]["name"], p2_resolver["value"]))
        return

    def handle_negate_damage(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):
        if p1_resolver_l:
            for p1_resolver in p1_resolver_l:
                if "self-" in p1_resolver["name"]:
                    p1_resolver["name"] = p1_resolver["name"].replace("self-", "")
                if p1_resolver["name"] == "immune-to-damage":
                    game_state["p1"]["status"]["immune-to-damage"] = game_state["p1"]["current-hp"]
                elif "negate-damage" in game_state["p1"]["status"]:
                    game_state["p1"]["status"]["negate-damage"] = game_state["p1"]["status"]["negate-damage"] + p1_resolver["value"]

                else:
                    game_state["p1"]["status"]["negate-damage"] = p1_resolver["value"]
                if p1_resolver["name"] == "block-impale":
                    game_state["p1"]["status"]["perfect-negate-damage-impale"] = 1
                else:
                    game_state["p1"]["status"]["perfect-negate-damage"] = 1
                game_state["logs"].append(p1_resolver["verbose-text-past"]
                                          .format(game_state["p1"]["player"]["name"], p1_resolver["value"]))
        if p2_resolver_l:
            for p2_resolver in p2_resolver_l:
                if "self-" in p2_resolver["name"]:
                    p2_resolver["name"] = p2_resolver["name"].replace("self-", "")
                if p2_resolver["name"] == "immune-to-damage":
                    game_state["p2"]["status"]["immune-to-damage"] = game_state["p2"]["current-hp"]
                elif "negate-damage" in game_state["p2"]["status"]:
                    game_state["p2"]["status"]["negate-damage"] = game_state["p2"]["status"]["negate-damage"] + p2_resolver[
                        "value"]
                else:
                    game_state["p2"]["status"]["negate-damage"] = p2_resolver["value"]
                if p2_resolver["name"] == "block-impale":
                    game_state["p2"]["status"]["perfect-negate-damage-impale"] = 1
                else:
                    game_state["p2"]["status"]["perfect-negate-damage"] = 1
                game_state["logs"].append(p2_resolver["verbose-text-past"]
                                          .format(game_state["p2"]["player"]["name"], p2_resolver["value"]))
        return

    def handle_counter(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):

        if p1_resolver_l:
            for p1_resolver in p1_resolver_l:
                if "range" in p1_resolver and p1_resolver["range"] > 0:
                    if abs(game_state["p1"]["position"] - game_state["p2"]["position"]) > p1_resolver["range"]:
                        game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                                  .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                  "the opponent was out of range!"))
                        return
                if "negate-damage" in game_state["p2"]["status"] and game_state["p2"]["status"]["negate-damage"] > 0:
                    game_state["p2"]["status"]["negate-damage"] = 0

                    game_state["logs"].append(p1_resolver["verbose-text-past"]
                                              .format(game_state["p1"]["player"]["name"], p1_resolver["value"]))
                else:
                    game_state["p2"]["status"]["negate-damage"] = 0

                    game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                              .format(game_state["p1"]["player"]["name"], p1_resolver["value"], "the opponent had"
                                                                                                                 " no damage negation!"))
        if p2_resolver_l:
            for p2_resolver in p2_resolver_l:
                if "range" in p2_resolver and p2_resolver["range"] > 0:
                    if abs(game_state["p1"]["position"] - game_state["p2"]["position"]) > p2_resolver["range"]:
                        game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                                  .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                  "the opponent was out of range!"))
                        return
                if "negate-damage" in game_state["p1"]["status"] and game_state["p1"]["status"]["negate-damage"] > 0:
                    game_state["p1"]["status"]["negate-damage"] = 0

                    game_state["logs"].append(p2_resolver["verbose-text-past"]
                                              .format(game_state["p2"]["player"]["name"], p2_resolver["value"]))
                else:
                    game_state["p1"]["status"]["negate-damage"] = 0
                    game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                              .format(game_state["p2"]["player"]["name"], p2_resolver["value"], "the opponent had"
                                                                                                                 " no damage negation!"))
        return

    def handle_damage(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta, self_dmg=False):
        if p1_resolver_l:
            for p1_resolver in p1_resolver_l:
                if "range" in p1_resolver and p1_resolver["range"] > 0:
                    if not self_dmg or p1_resolver["name"] == "self-recoil-damage":
                        if abs(game_state["p1"]["position"] - game_state["p2"]["position"]) > p1_resolver["range"]:
                            game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                                      .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                      "the opponent was out of range!"))
                            return
                self.handle_solo_damage(game_state, "p1", p1_resolver, self_dmg)
        if p2_resolver_l:
            for p2_resolver in p2_resolver_l:
                if "range" in p2_resolver and p2_resolver["range"] > 0:
                    if not self_dmg or p2_resolver["name"] == "self-recoil-damage":
                        if abs(game_state["p2"]["position"] - game_state["p1"]["position"]) > p2_resolver["range"]:
                            game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                                      .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                      "the opponent was out of range!"))
                            return
                self.handle_solo_damage(game_state, "p2", p2_resolver, self_dmg)

    def handle_self_damage(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):
        self.handle_damage(game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta, True)


    def handle_solo_damage(self, game_state, player_num, resolver, self_dmg=False):
        if self_dmg:
            opp_num = player_num
        else:
            if player_num == "p1":
                opp_num = "p2"
            else:
                opp_num = "p1"

        val = resolver["value"]
        if resolver["name"] == "damage-boost":
            card_played_counter = 0
            for step in game_state[player_num]["next-turn"]["steps"]:
                if step["name"] == "card":
                    card_played_counter = card_played_counter + 1
            val = card_played_counter * int(val)
        elif resolver["name"] == "damage-double-empower-consume":
            if "empower" in game_state[player_num]["status"]:
                val = (int(game_state[player_num]["status"]["empower"]) * 2) + int(val)
                game_state[player_num]["status"]["empower"] = 0
        elif resolver["name"] == "damage-double-impale":
            if "impale" in game_state[opp_num]["status"]:
                val = (int(game_state[opp_num]["status"]["impale"]) * 2) + int(val)
                game_state[opp_num]["status"]["impale"] = 0
        elif resolver["name"] == "damage-minus-movement-actions":
            move_counter = 0
            for step in game_state[player_num]["next-turn"]["steps"]:
                if step["type"] == "movement":
                    move_counter = move_counter + 1

            val = int(val) - move_counter
            if val < 0:
                val = 0
        player_data = game_state[player_num]

        if not self_dmg:
            if "empower" in player_data["status"] and player_data["status"]["empower"] > 0:
                val = int(val) + 1
                player_data["status"]["empower"] = player_data["status"]["empower"] - 1
        opp_data = game_state[opp_num]

        if "negate-damage" in opp_data["status"] and opp_data["status"]["negate-damage"] > 0:
            opp_data["status"]["negate-damage"] = opp_data["status"]["negate-damage"] - 1

            if "perfect-negate-damage" in opp_data["status"] and opp_data["status"]["perfect-negate-damage"] > 0:
                game_state["logs"].append(resolver["verbose-text-failed"]
                                          .format(game_state[player_num]["player"]["name"], str(val),
                                                  "the opponent perfectly timed a block!!"))
                if "perfect-block-draw" in opp_data:
                    opp_data["status"]["perfect-block-draw"] = opp_data["status"]["perfect-block-draw"]
                else:
                    opp_data["status"]["perfect-block-draw"] = 1
            elif "perfect-negate-damage-impale" in opp_data["status"] and opp_data["status"]["perfect-negate-damage-impale"] > 0:
                game_state["logs"].append(resolver["verbose-text-failed"]
                                          .format(game_state[player_num]["player"]["name"], str(val),
                                                  "the opponent perfectly timed a block and impaled them!!"))
                if "impale" in player_data["status"]:
                    player_data["status"]["impale"] = player_data["status"]["impale"] + 2
                else:
                    player_data["status"]["impale"] = 2
            else:
                if not self_dmg:
                    game_state["logs"].append(resolver["verbose-text-failed"]
                                              .format(game_state[player_num]["player"]["name"], str(val),
                                                      "the opponent had an instance of damage negation!!"))
                else:
                    game_state["logs"].append(resolver["verbose-text-failed"]
                                              .format(game_state[player_num]["player"]["name"], str(val),
                                                      "they prevented self-damage using prior damage negation!"))
        else:
            opp_data["current-hp"] = int(opp_data["current-hp"]) - int(val)
            game_state["logs"].append(resolver["verbose-text-past"]
                                  .format(game_state[player_num]["player"]["name"], str(val)))
            game_state["logs"].append("{0} now has {1} HP!".format(game_state[opp_num]["player"]["name"], game_state[opp_num]["current-hp"]))
        return

    def handle_self_debuff(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):
        if p1_resolver_l:
            for p1_resolver in p1_resolver_l:
                status = p1_resolver["name"]
                if "self-" in status:
                    status = status.replace("self-", "")
                if status in game_state["p1"]["status"]:
                    if type(game_state["p1"]["status"][status]) is dict:
                        if status == "teleport-to-position":
                            game_state["p1"]["status"][status] = {"turns-left": p1_resolver["value"],
                                                                  "position": game_state["p1"]["position"]}
                    else:
                        game_state["p1"]["status"][status] = int(game_state["p1"]["status"][status]) + int(p1_resolver[
                                                                                                               "value"])
                else:
                    if status == "teleport-to-position":
                        game_state["p1"]["status"][status] = {"turns-left": p1_resolver["value"],
                                                              "position": game_state["p1"]["position"]}
                    else:
                        game_state["p1"]["status"][status] = int(p1_resolver["value"])

                game_state["logs"].append(p1_resolver["verbose-text-past"]
                                          .format(game_state["p1"]["player"]["name"], p1_resolver["value"]))
        if p2_resolver_l:
            for p2_resolver in p2_resolver_l:
                status = p2_resolver["name"]
                if "self-" in status:
                    status = status.replace("self-", "")
                if status in game_state["p2"]["status"]:
                    if type(game_state["p2"]["status"][status]) is dict:
                        if status == "teleport-to-position":
                            game_state["p2"]["status"][status] = {"turns-left": p2_resolver["value"],
                                                                  "position": game_state["p2"]["position"]}
                    else:
                        game_state["p2"]["status"][status] = int(game_state["p2"]["status"][status]) + int(p2_resolver[
                                                                                                               "value"])
                else:
                    if status == "teleport-to-position":
                        game_state["p2"]["status"][status] = {"turns-left": p2_resolver["value"],
                                                              "position": game_state["p2"]["position"]}
                    else:
                        game_state["p2"]["status"][status] = int(p2_resolver["value"])
                game_state["logs"].append(p2_resolver["verbose-text-past"]
                                          .format(game_state["p2"]["player"]["name"], p2_resolver["value"]))
        return

    def handle_debuff(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):
        if p1_resolver_l:
            for p1_resolver in p1_resolver_l:
                status = p1_resolver["name"]
                if "inflict-" in status:
                    status = status.replace("inflict-", "")
                if "range" in p1_resolver and p1_resolver["range"] > 0:
                    if abs(game_state["p1"]["position"] - game_state["p2"]["position"]) > p1_resolver["range"]:
                        game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                                  .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                  "the opponent was out of range!"))
                        continue
                """
                # This is for the future if we want to negate buffs on perfect timing
                if game_state["p2"]["status"]["perfect-negate-damage"] > 0:
                    if abs(game_state["p1"]["position"] - game_state["p2"]["position"]) > p1_resolver["range"]:
                        game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                                  .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                  "the opponent perfectly blocked!"))
                
                    return
                """
                # conditional statuses that change to other statuses
                if status == "chilled-if-impale-four":
                    if "impale" in game_state["p2"]["status"] and game_state["p2"]["status"]["impale"] >= 4:
                        if "chilled" in game_state["p2"]["status"]:
                            game_state["p2"]["status"]["chilled"] = game_state["p2"]["status"]["chilled"] + p1_resolver["value"]
                        else:
                            game_state["p2"]["status"]["chilled"] = p1_resolver["value"]
                    else:
                        game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                                  .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                          "the opponent didn't have enough impale stacks!"))
                        continue
                # if the status exists
                elif status in game_state["p2"]["status"]:
                    if type(game_state["p2"]["status"][status]) is dict:
                        # just overwrite teleports
                        if status == "teleport-to-position":
                            game_state["p2"]["status"][status] = {"turns-left": p1_resolver["value"], "position": game_state["p2"]["position"]}
                    else:
                        game_state["p2"]["status"][status] = int(game_state["p2"]["status"][status]) + int(p1_resolver["value"])
                # if the status doesn't exist
                else:
                    if status == "teleport-to-position":
                        game_state["p2"]["status"][status] = {"turns-left": p1_resolver["value"], "position": game_state["p2"]["position"]}
                    else:
                        game_state["p2"]["status"][status] = p1_resolver["value"]

                game_state["logs"].append(p1_resolver["verbose-text-past"]
                                          .format(game_state["p1"]["player"]["name"], p1_resolver["value"]))
        if p2_resolver_l:
            for p2_resolver in p2_resolver_l:
                status = p2_resolver["name"]
                if "inflict-" in status:
                    status = status.replace("inflict-", "")
                if "range" in p2_resolver and p2_resolver["range"] > 0:
                    if abs(game_state["p2"]["position"] - game_state["p1"]["position"]) > p2_resolver["range"]:
                        game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                                  .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                  "the opponent was out of range!"))
                        continue
                """"
                # For the future if we want to negate debuffs on perfect
                if game_state["p1"]["status"]["perfect-negate-damage"] > 0:
                    if abs(game_state["p2"]["position"] - game_state["p1"]["position"]) > p2_resolver["range"]:
                        game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                                  .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                  "the opponent perfectly blocked!"))
                        return
                """
                # conditional statuses that change to other statuses
                if status == "chilled-if-impale-four":
                    if "impale" in game_state["p1"]["status"] and game_state["p1"]["status"]["impale"] >= 4:
                        if "chilled" in game_state["p1"]["status"]:
                            game_state["p1"]["status"]["chilled"] = game_state["p1"]["status"]["chilled"] + p2_resolver[
                                "value"]
                        else:
                            game_state["p1"]["status"]["chilled"] = p2_resolver["value"]
                    else:
                        game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                                  .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                          "the opponent didn't have enough impale stacks!"))
                        continue
                # if the status exists
                elif status in game_state["p1"]["status"]:
                    if type(game_state["p1"]["status"][status]) is dict:
                        if status == "teleport-to-position":
                            game_state["p1"]["status"][status] = {"turns-left": p2_resolver["value"], "position": game_state["p1"]["position"]}
                    else:
                        game_state["p1"]["status"][status] = int(game_state["p1"]["status"][status]) + int(p2_resolver["value"])
                else:
                    if status == "teleport-to-position":
                        game_state["p1"]["status"][status] = {"turns-left": p2_resolver["value"],
                                                              "position": game_state["p1"]["position"]}
                    else:
                        game_state["p1"]["status"][status] = p2_resolver["value"]
                game_state["logs"].append(p2_resolver["verbose-text-past"]
                                          .format(game_state["p2"]["player"]["name"], p2_resolver["value"]))
        return

    def handle_buff(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):
        if p1_resolver_l:
            for p1_resolver in p1_resolver_l:
                status = p1_resolver["name"]
                if "self-" in status:
                    status = status.replace("self-", "")
                if status in game_state["p1"]["status"]:
                    game_state["p1"]["status"][status] = int(game_state["p1"]["status"][status]) + int(p1_resolver[
                        "value"])
                else:
                    game_state["p1"]["status"][status] = int(p1_resolver["value"])

                game_state["logs"].append(p1_resolver["verbose-text-past"]
                                          .format(game_state["p1"]["player"]["name"], p1_resolver["value"]))

        if p2_resolver_l:
            for p2_resolver in p2_resolver_l:
                status = p2_resolver["name"]
                if "self-" in status:
                    status = status.replace("self-", "")

                if status in game_state["p2"]["status"]:
                    game_state["p2"]["status"][status] = int(game_state["p2"]["status"][status]) + int(p2_resolver[
                                                                                                           "value"])
                else:
                    game_state["p2"]["status"][status] = int(p2_resolver["value"])
                game_state["logs"].append(p2_resolver["verbose-text-past"]
                                          .format(game_state["p2"]["player"]["name"], p2_resolver["value"]))

        return

    def handle_opponent_buff(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):
        if p1_resolver_l:
            for p1_resolver in p1_resolver_l:
                if "range" in p1_resolver and p1_resolver["range"] > 0:
                    if abs(game_state["p1"]["position"] - game_state["p2"]["position"]) > p1_resolver["range"]:
                        game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                                  .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                  "the opponent was out of range!"))
                        return
                if p1_resolver["name"] in game_state["p2"]["status"]:
                    game_state["p2"]["status"][p1_resolver["name"]] = game_state["p2"]["status"][p1_resolver["name"]] + p1_resolver[
                        "value"]
                else:
                    game_state["p2"]["status"][p1_resolver["name"]] = p1_resolver["value"]

                game_state["logs"].append(p1_resolver["verbose-text-past"]
                                          .format(game_state["p1"]["player"]["name"], p1_resolver["value"]))
        if p2_resolver_l:
            for p2_resolver in p2_resolver_l:
                if "range" in p2_resolver and p2_resolver["range"] > 0:
                    if abs(game_state["p2"]["position"] - game_state["p1"]["position"]) > p2_resolver["range"]:
                        game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                                  .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                  "the opponent was out of range!"))
                if p2_resolver["name"] in game_state["p1"]["status"]:
                    game_state["p1"]["status"][p2_resolver["name"]] = game_state["p1"]["status"][p2_resolver["name"]] + p2_resolver[
                        "value"]
                else:
                    game_state["p1"]["status"][p2_resolver["name"]] = p2_resolver["value"]
                game_state["logs"].append(p2_resolver["verbose-text-past"]
                                          .format(game_state["p2"]["player"]["name"], p2_resolver["value"]))
        return

    def handle_late_movement(self, game_state, p1_resolver, p2_resolver, is_card_p1, is_card_p2, meta):
        self.handle_movement(game_state, p1_resolver, p2_resolver, is_card_p1, is_card_p2, meta)

    def handle_draw(self, game_state, p1_resolver_l, p2_resolver_l, is_card_p1, is_card_p2, meta):
        if p1_resolver_l:
            for p1_resolver in p1_resolver_l:
                if "chilled" in game_state["p1"]["status"] and game_state["p1"]["status"]["chilled"] and meta["p1-non-card-action-count"] >= 2 and not is_card_p1:
                    game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                              .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                      " was chilled!"))
                    continue
                if p1_resolver["name"] == "draw-pressure-if-impale-five":
                    if "impale" in game_state["p2"]["status"] and game_state["p2"]["status"]["impale"] >= 5:
                        p1_resolver["name"] = "draw-pressure"
                    else:
                        game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                                  .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                          "the opponent didn't have 5 impale stacks!"))
                        continue
                if len(game_state["p1"]["hand"]) < 10:
                    if p1_resolver["name"] == "draw-pressure":
                        self.draw_cards_from_deck(game_state["p1"]["hand"], game_state["p1"]["pressure-deck"],
                                                  p1_resolver["value"],game_state["p1"]["discard"] , "pressure")
                    if p1_resolver["name"] == "draw-options":
                        self.draw_cards_from_deck(game_state["p1"]["hand"], game_state["p1"]["options-deck"],
                                                  p1_resolver["value"], game_state["p1"]["discard"], "options")
                    game_state["logs"].append(p1_resolver["verbose-text-past"]
                                          .format(game_state["p1"]["player"]["name"], p1_resolver["value"]))
                else:
                    game_state["logs"].append(p1_resolver["verbose-text-failed"]
                                                  .format(game_state["p1"]["player"]["name"], p1_resolver["value"],
                                                  "hand was full!"))
        if p2_resolver_l:
            for p2_resolver in p2_resolver_l:
                if "chilled" in game_state["p2"]["status"] and game_state["p2"]["status"]["chilled"] and meta["p2-non-card-action-count"] >= 2 and not is_card_p2:
                    game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                              .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                      " was chilled!"))
                    continue
                if p2_resolver["name"] == "draw-pressure-if-impale-five":
                    if "impale" in game_state["p1"]["status"] and game_state["p1"]["status"]["impale"] >= 5:
                        p2_resolver["name"] = "draw-pressure"
                    else:
                        game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                                  .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                          "the opponent didn't have 5 impale stacks!"))
                        continue
                if len(game_state["p2"]["hand"]) < 10:
                    if p2_resolver["name"] == "draw-pressure":
                        self.draw_cards_from_deck(game_state["p2"]["hand"], game_state["p2"]["pressure-deck"],
                                                  p2_resolver["value"],game_state["p2"]["discard"] , "pressure")
                    if p2_resolver["name"] == "draw-options":
                        self.draw_cards_from_deck(game_state["p2"]["hand"], game_state["p2"]["options-deck"],
                                                  p2_resolver["value"], game_state["p2"]["discard"], "options")
                    game_state["logs"].append(p2_resolver["verbose-text-past"]
                                              .format(game_state["p2"]["player"]["name"], p2_resolver["value"]))
                else:
                    game_state["logs"].append(p2_resolver["verbose-text-failed"]
                                                  .format(game_state["p2"]["player"]["name"], p2_resolver["value"],
                                                  "hand was full!"))

        return

    # Pre-checks, like interrupted or mana cost checks here
    def construct_step_resolver(self, db, game_state, player1_data, p1_step, p1_platonic_step, hand1, meta):
        p1_resolver = {}
        if "interrupted" in player1_data["status"] and player1_data["status"]["interrupted"] > 0:
            player1_data["status"]["interrupted"] = player1_data["status"]["interrupted"] - 1
            if p1_step["name"] =="card":
                c = hand1.pop(int(p1_step["value"]))
                game_state["logs"].append(p1_platonic_step["verbose-text-failed"]
                                          .format(player1_data["player"]["name"], c["name"],
                                                  " was interrupted!"))
                hand1.append(c)
                return p1_resolver
            game_state["logs"].append(p1_platonic_step["verbose-text-failed"]
                                      .format(player1_data["player"]["name"], p1_step["value"] ,
                                              " was interrupted!"))
            return p1_resolver
        elif p1_step["name"] == "card":
            card = hand1.pop(int(p1_step["value"]))
            # check mana and status to see if it can be played, if not, card is popped from hand then returned to it

            if card["current-mana"] > player1_data["mana"]:
                game_state["logs"].append(p1_platonic_step["verbose-text-failed"]
                                          .format(player1_data["player"]["name"], card["name"],
                                                  " but didn't have enough mana!"))
                hand1.append(card)
                return p1_resolver
            else:
                # if it can, pop the card and move it to discard. then (later) iterate through opponent hand and discount options

                if card["deck"] == "options":
                    # check for off balance
                    if "off-balance" in player1_data["status"] and player1_data["status"]["off-balance"] and int(player1_data["status"]["off-balance"]) > 0:
                        game_state["logs"].append(p1_platonic_step["verbose-text-failed"]
                                                  .format(player1_data["player"]["name"], card["name"],
                                                          " was off-balance, so couldn't play an options card!"))
                        hand1.append(card)
                        return p1_resolver
                    else:
                        for discount_card in hand1:
                            if discount_card["deck"] == "pressure" and discount_card["current-mana"] > 1:
                                discount_card["current-mana"] = discount_card["current-mana"] - 1
                        player1_data["mana"] = player1_data["mana"] - card["current-mana"]
                        card["current-mana"] = card["mana"]
                player1_data["discard"].append(card)

                game_state["logs"].append(" -- **" + p1_platonic_step["verbose-text-past"]
                                          .format(player1_data["player"]["name"], card["name"]) + "** --")

                # Check for card buffs
                if "next-card-shatter" in player1_data["status"] and player1_data["status"]["next-card-shatter"] > 0:
                    if "damage" in card["tags"]:
                        p1_step["sub-steps"]["shatter"] = 1
                        warning = "This card is buffed to have a Shatter effect!"
                        game_state["logs"].append(warning)
                        player1_data["status"]["next-card-shatter"] = player1_data["status"]["next-card-shatter"] - 1
                    if player1_data["status"]["next-card-shatter"] <= 0:
                        player1_data["status"].pop("next-card-shatter", None)
                # Check for card buffs
                if "range-buff-2" in player1_data["status"] and player1_data["status"]["range-buff-2"] > 0:
                    if "damage" in card["tags"]:
                        card["range"] = card["range"] + 2
                        warning = "This card is buffed to have with +2 range!"
                        game_state["logs"].append(warning)
                        player1_data["status"]["range-buff-2"] = player1_data["status"]["range-buff-2"] - 1
                    if player1_data["status"]["range-buff-2"] <= 0:
                        player1_data["status"].pop("range-buff-2", None)

                for effect in p1_step["sub-steps"]:
                    substep_doc = db.collection(u'fg-log-steps').document(effect).get()
                    if not substep_doc.exists:
                        raise Exception(
                            "Step `{0}` was not recognized. Please contact <@116045478709297152>, this is a bug.".format(
                                effect))
                    platonic_substep = substep_doc.to_dict()


                    if platonic_substep["type"] in p1_resolver:
                        p1_resolver[platonic_substep["type"]].append({"name": effect,
                                       "value": p1_step["sub-steps"][effect],
                                       "type": platonic_substep["type"],
                                       "verbose-text-past": platonic_substep["verbose-text-past"],
                                       "verbose-text-failed": platonic_substep["verbose-text-failed"],
                                                                      "range": card["range"]
                                       })
                    else:
                        p1_resolver[platonic_substep["type"]] = [{"name": effect,
                                       "value": p1_step["sub-steps"][effect],
                                       "type": platonic_substep["type"],
                                       "verbose-text-past": platonic_substep["verbose-text-past"],
                                       "verbose-text-failed": platonic_substep["verbose-text-failed"],
                                                                  "range": card["range"]
                                       }]
        else:

            p1_resolver[p1_step["type"]] = [{"name": p1_step["name"],
                                   "value": p1_step["value"],
                                   "type": p1_step["type"],
                                   "verbose-text-past": p1_platonic_step["verbose-text-past"],
                                   "verbose-text-failed": p1_platonic_step["verbose-text-failed"]
                                   }]
        return p1_resolver





    async def check_for_end_game_and_update_active_fights(self, db, discord_client, game_state, fight_id):
        hp1 = game_state["p1"]["current-hp"]
        hp2 = game_state["p2"]["current-hp"]
        if hp1 <= 0 or hp2 <= 0 or game_state["round"] > 15:
            if game_state["round"] > 15:
                if hp1 > hp2:
                    winner = "p1"
                elif hp2 > hp1:
                    winner = "p2"
                else:
                    winner = "tie"
            if hp1 <= 0 and hp2 <= 0:
                winner = "tie"
            elif hp1 <= 0:
                winner = "p2"
            elif hp2 <= 0:
                winner = "p1"

            if winner != "tie":
                game_state["logs"].append("\n\n**{0} WINS**".format(game_state[winner]["player"]["name"]))
            else:
                game_state["logs"].append("\n\n**Tie!**")
            await self.update_fight_data_complete(discord_client, db, game_state, fight_id, winner)
            return True
        else:
            return False

    async def update_fight_data_complete(self, discord_client, db, fight_data, fight_id, winner):

        p1_embeds = self.render_embeds(fight_data, "p1", winner)
        p2_embeds = self.render_embeds(fight_data, "p2", winner)

        p1_msg_meta = fight_data["metadata"]["p1"]
        p1_state_id = p1_msg_meta["state_msg"]
        p1_channel_id = p1_msg_meta["channel"]
        p1_log_id = p1_msg_meta["log_msg"]
        p1_hand_id = p1_msg_meta["hand_msg"]
        p1_conf_id = p1_msg_meta["turn_confirmation_msg"]

        p2_msg_meta = fight_data["metadata"]["p2"]
        p2_state_id = p2_msg_meta["state_msg"]
        p2_channel_id = p2_msg_meta["channel"]
        p2_log_id = p2_msg_meta["log_msg"]
        p2_hand_id = p2_msg_meta["hand_msg"]
        p2_conf_id = p2_msg_meta["turn_confirmation_msg"]

        spec_msg_meta = fight_data["metadata"]["spec"]
        spec_state_id = spec_msg_meta["state_message"]
        spec_channel_id = spec_msg_meta["channel"]
        spec_log_id = spec_msg_meta["log_msg"]

        p1_channel = await discord_client.fetch_channel(p1_channel_id)
        p1_state_msg = await p1_channel.fetch_message(p1_state_id)
        p1_log_msg = await p1_channel.fetch_message(p1_log_id)
        p1_hand_msg = await p1_channel.fetch_message(p1_hand_id)
        p1_conf_msg = await p1_channel.fetch_message(p1_conf_id)
        await p1_state_msg.edit(embed=p1_embeds["fight_state"])
        await p1_log_msg.edit(embed=p1_embeds["log"])
        await p1_hand_msg.delete()
        await p1_conf_msg.delete()

        p2_channel = await discord_client.fetch_channel(p2_channel_id)
        p2_state_msg = await p2_channel.fetch_message(p2_state_id)
        p2_log_msg = await p2_channel.fetch_message(p2_log_id)
        p2_hand_msg = await p2_channel.fetch_message(p2_hand_id)
        p2_conf_msg = await p2_channel.fetch_message(p2_conf_id)
        await p2_state_msg.edit(embed=p2_embeds["fight_state"])
        await p2_log_msg.edit(embed=p2_embeds["log"])
        await p2_hand_msg.delete()
        await p2_conf_msg.delete()

        spec_channel = await discord_client.fetch_channel(spec_channel_id)
        spec_state_msg = await spec_channel.fetch_message(spec_state_id)
        spec_log_msg = await spec_channel.fetch_message(spec_log_id)
        await spec_state_msg.edit(embed=p1_embeds["fight_state"])
        await spec_log_msg.edit(embed=p1_embeds["log"])

        try:
            db.collection(u'fg-hands-fights').document(str(p1_hand_id)).delete()
            db.collection(u'fg-hands-fights').document(str(p2_hand_id)).delete()

            pfd1 = db.collection(u'fg-player-fights').document(str(fight_data["p1"]["id"]))
            pfd2 = db.collection(u'fg-player-fights').document(str(fight_data["p2"]["id"]))

            pf1 = pfd1.get().to_dict()
            pf2 = pfd2.get().to_dict()

            pf1["active-fights"].pop(str(fight_data["p2"]["id"]), None)
            pf2["active-fights"].pop(str(fight_data["p1"]["id"]), None)

            if winner != "tie":
                winner_id = fight_data[winner]["id"]
            else:
                winner_id = "tie"

            if str(fight_data["p2"]["id"]) not in pf1["complete-fights"]:
                pf1["complete-fights"][str(fight_data["p2"]["id"])] = []
            if str(fight_data["p1"]["id"]) not in pf2["complete-fights"]:
                pf2["complete-fights"][str(fight_data["p1"]["id"])] = []
            pf1["complete-fights"][str(fight_data["p2"]["id"])].append({"fight-id": fight_id, "winner-id": winner_id})
            pf2["complete-fights"][str(fight_data["p1"]["id"])].append({"fight-id": fight_id, "winner-id": winner_id})

            pfd1.set(pf1)
            pfd2.set(pf2)

        except Exception as e:
            print(e)
            raise e
            return

    async def update_render_entire_fight_from_fight_metadata(self, discord_client, fight_data, hand_update=None, opponent_data=None):

        p1_embeds = self.render_embeds(fight_data, "p1")
        p2_embeds = self.render_embeds(fight_data, "p2")

        if hand_update is not None:
            if list(hand_update)[0] == "p1":
                p1_embeds["hand"] = hand_update["p1"]
            else:
                p2_embeds["hand"] = hand_update["p2"]

        if opponent_data and opponent_data == "p1":
            skip_p1 = True
            skip_p2 = False
        elif opponent_data and opponent_data == "p2":
            skip_p2 = True
            skip_p1 = False
        else:
            skip_p1 = False
            skip_p2 = False


        p1_msg_meta = fight_data["metadata"]["p1"]
        p1_state_id = p1_msg_meta["state_msg"]
        p1_channel_id = p1_msg_meta["channel"]
        p1_log_id = p1_msg_meta["log_msg"]
        p1_hand_id = p1_msg_meta["hand_msg"]
        p1_conf_id = p1_msg_meta["turn_confirmation_msg"]

        p2_msg_meta = fight_data["metadata"]["p2"]
        p2_state_id = p2_msg_meta["state_msg"]
        p2_channel_id = p2_msg_meta["channel"]
        p2_log_id = p2_msg_meta["log_msg"]
        p2_hand_id = p2_msg_meta["hand_msg"]
        p2_conf_id = p2_msg_meta["turn_confirmation_msg"]

        spec_msg_meta = fight_data["metadata"]["spec"]
        spec_state_id = spec_msg_meta["state_message"]
        spec_channel_id = spec_msg_meta["channel"]
        spec_log_id = spec_msg_meta["log_msg"]

        p1_channel = await discord_client.fetch_channel(p1_channel_id)
        p1_state_msg = await p1_channel.fetch_message(p1_state_id)
        p1_log_msg = await p1_channel.fetch_message(p1_log_id)

        await p1_state_msg.edit(embed=p1_embeds["fight_state"])
        await p1_log_msg.edit(embed=p1_embeds["log"])
        if not skip_p1:
            p1_hand_msg = await p1_channel.fetch_message(p1_hand_id)
            p1_conf_msg = await p1_channel.fetch_message(p1_conf_id)
            await p1_hand_msg.edit(embed=p1_embeds["hand"])
            await p1_conf_msg.edit(embed=p1_embeds["turn_confirmation"])

        p2_channel = await discord_client.fetch_channel(p2_channel_id)
        p2_state_msg = await p2_channel.fetch_message(p2_state_id)
        p2_log_msg = await p2_channel.fetch_message(p2_log_id)
        await p2_state_msg.edit(embed=p2_embeds["fight_state"])
        await p2_log_msg.edit(embed=p2_embeds["log"])
        if not skip_p2:
            p2_hand_msg = await p2_channel.fetch_message(p2_hand_id)
            p2_conf_msg = await p2_channel.fetch_message(p2_conf_id)
            await p2_hand_msg.edit(embed=p2_embeds["hand"])
            await p2_conf_msg.edit(embed=p2_embeds["turn_confirmation"])

        spec_channel = await discord_client.fetch_channel(spec_channel_id)
        spec_state_msg = await spec_channel.fetch_message(spec_state_id)
        spec_log_msg = await spec_channel.fetch_message(spec_log_id)
        await spec_state_msg.edit(embed=p1_embeds["fight_state"])
        await spec_log_msg.edit(embed=p1_embeds["log"])


    def render_abstract_hand(self, hand):
        hand_string = ""
        for card in hand:
            if card["deck"] == "pressure":
                hand_string = hand_string + "🟥"
            elif card["deck"] == "options":
                hand_string = hand_string + "🟦"
        if hand_string == "":
            hand_string = "No cards in hand!"
        return hand_string

    def render_non_card_actions(self, embed):
        embed.add_field(name="⬅️: Move Left", value="Moves your character left", inline=True)
        embed.add_field(name="➡️:  Move Right", value="Moves your character right ", inline=True)
        embed.add_field(name="⭐: Regenerate Mana", value="Regenerate a mana\n", inline=True)
        embed.add_field(name="🔴:  Draw Pressure Card ",
                        value="Draw a pressure card:\nAggressive damage and combo finishers. \n", inline=True)
        embed.add_field(name="🔵:  Draw Options Card",
                        value="Draw an options card:\nDefensive options and combo pieces.\n ", inline=True)

    def render_card(self, embed, card, emoji=None):
        deck_emoji = ""
        if card["deck"] == "pressure":
            deck_emoji = "🟥"
        if card["deck"] == "options":
            deck_emoji = "🟦"
        v = "{0}{0}{0}{0}{0}{0}{0}{0}{0}{0}{0} {1} {0}{0}{0}{0}{0}{0}{0}{0}{0}{0}{0}\n" \
            "\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\n" \
            "**{8}** {9}: *{2}*\n\n\n\n" \
            "{3}\n\n\n" \
            "---------------------------- /  Cost: {4}  /  Range: {5}  /  Dmg: {6}  / ----------------------------\n" \
            "*{7}*\n" \
            "\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\n"\
            .format(deck_emoji, card["deck"], ", ".join(card["tags"]), card["description"] , card["mana"],
                    card["range"], card["damage"], card["flavor"], card["name"], card["image"])
        if emoji:
            embed.add_field(name="{0} : {1} {2}".format(emoji, card["name"], card["image"]), value=v, inline=False)
        else:
            embed.add_field(name="{0} {1}".format(card["name"], card["image"]), value=v, inline=False)

    def render_compact_card_in_one_embed(self, embed, card, emoji=None, platonic=False):
        if platonic:
            mana = "mana"
        else:
            mana = "current-mana"
        if card["deck"] == "pressure":
            deck_emoji = "🟥 (Pressure)"
        if card["deck"] == "options":
            deck_emoji = "🟦 (Options)"
        v = "Cost: {0} /Range: {1} \nDamage:{2}\nDescription:\n{3}\nDeck: {4}".format(card[mana],
                    card["range"], card["damage"],card["description"], deck_emoji)
        if emoji is not None:
            embed.add_field(name="{0} : {1} {2}".format(emoji, card["name"], card["image"]), value=v, inline=True)
        else:
            embed.add_field(name="{0} {1}".format(card["name"], card["image"]), value=v, inline=True)

    def render_reveal_hand_embed(self, db,  player_data):
        # this function can only be executed if actions-submitted = true and submitted = false
        # render hand without any actions and only with cards that are not submitted
        # render hand without any
        return

    async def clear_turn_plan_and_rerender_hand_embed(self, discord_client, db, fight_id, fight_data, player_number, turn_conf_msg_id, payload, channel_obj):
        # this function can only be executed if submitted = false
        # set actions-submitted to false,clear steps array
        turn = fight_data[player_number]["next-turn"]
        if not turn["submitted"]:
            channel = await discord_client.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(turn_conf_msg_id)
            embed = discord.Embed(title="Next Turn Plan", colour=discord.Colour(0xd0021b),
                                  description="",
                                  timestamp=datetime.datetime.now().astimezone(timezone('US/Pacific')))
            await message.edit(embed=embed)

            # rerender hand
            hand_message = await channel.fetch_message(payload.message_id)
            await hand_message.edit(embed=self.create_hand_embed(fight_data, player_number))
            ref = db.collection(u'fg-fights').document(str(fight_id))

            ref.update({db.field_path(str(player_number), "next-turn"):
                    {
                        u'actions-submitted': False,
                        u'reveal': -1,
                        u'steps': [],
                        u'submitted': False
                    }})
            await channel_obj.send("Cleared the turn confirmation")
        else:
            await channel_obj.send("You already submitted your turn!")

        return

    def render_embeds(self, fight_data, player_data=None, winner=None):
        return_embed = {}

        arena = "| \\_\\_\\_ \\_\\_\\_ \\_\\_\\_ \\_\\_\\_ \\_\\_\\_ \\_\\_\\_ \\_\\_\\_ \\_\\_\\_ \\_\\_\\_ \\_\\_\\_ \\_\\_\\_ |"
        p1_pos = (fight_data["p1"]["position"] * 7) + 2
        p2_pos = (fight_data["p2"]["position"] * 7) + 2
        if p2_pos > p1_pos:
            arena = "{0}{1} {2}".format(arena[:p2_pos], fight_data["p2"]["player"]["emoji"], arena[p2_pos + 6:])

            arena = "{0}{1} {2}".format(arena[:p1_pos], fight_data["p1"]["player"]["emoji"], arena[p1_pos + 6:])

        else:
            arena = "{0}{1} {2}".format(arena[:p1_pos], fight_data["p1"]["player"]["emoji"], arena[p1_pos + 6:])

            arena = "{0}{1} {2}".format(arena[:p2_pos], fight_data["p2"]["player"]["emoji"], arena[p2_pos + 6:])


        if winner is not None:
            if winner == "tie":
                title = "TIE!"
            else:
                title = "{0} WINS!".format(fight_data[winner]["player"]["name"])
        else:
            title = "FIGHT!"
        underground = "\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_"
        embed = discord.Embed(title=title, colour=discord.Colour(0xd0021b),
                              description="\n{0}\n{1}".format(arena, underground),
                              timestamp=datetime.datetime.now().astimezone(timezone('US/Pacific')))

        #embed.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/0.png")
        waiting = "both"
        if fight_data["p1"]["next-turn"]["submitted"]:
            waiting = "{0}".format(fight_data["p2"]["player"]["name"])
        elif fight_data["p2"]["next-turn"]["submitted"]:
            waiting = "{0}".format(fight_data["p1"]["player"]["name"])

        embed.set_footer(text="Round {0}: Waiting on {1} | Last Updated".format(fight_data["round"], waiting))

        embed.add_field(name="{0}".format(fight_data["p1"]["player"]["name"]),
                        value="{0}".format(fight_data["p1"]["player"]["emoji"]), inline=True)
        embed.add_field(name="{0}".format(fight_data["p2"]["player"]["name"]),
                        value="{0}".format(fight_data["p2"]["player"]["emoji"]), inline=True)

        embed.add_field(name="-----", value="-----", inline=False)
        embed.add_field(name="HP", value="{0}/{1}".format(fight_data["p1"]["current-hp"], fight_data["p1"]["max-hp"]), inline=True)
        embed.add_field(name="HP", value="{0}/{1}".format(fight_data["p2"]["current-hp"], fight_data["p2"]["max-hp"]), inline=True)
        embed.add_field(name="-----", value="-----", inline=False)
        embed.add_field(name="Status", value="{0}".format(str(fight_data["p1"]["status"])), inline=True)
        embed.add_field(name="Status", value="{0}".format(str(fight_data["p2"]["status"])), inline=True)
        embed.add_field(name="-----", value="-----", inline=False)
        p1_abstract_hand = self.render_abstract_hand(fight_data["p1"]["hand"])
        p2_abstract_hand = self.render_abstract_hand(fight_data["p2"]["hand"])

        embed.add_field(name="Hand", value="{0}".format(p1_abstract_hand), inline=True)
        embed.add_field(name="Hand", value="{0}".format(p2_abstract_hand), inline=True)

        return_embed["fight_state"] = embed
        log = "\n".join(fight_data["logs"])
        if len(log) >= 2000:
            log = log[-2000:]
        log_embed = discord.Embed(title="Logs", colour=discord.Colour(0xd0021b),
                              description="{0}".format(log),
                              timestamp=datetime.datetime.now().astimezone(timezone('US/Pacific')))
        return_embed["log"] = log_embed

        if player_data is not None:
            if winner is not None:
                if winner == "tie":
                    title = "TIE!"
                else:
                    title = "{0} WINS!".format(fight_data[winner]["player"]["name"])
                return_embed["turn_confirmation"] = discord.Embed(title="GAME OVER: {0}".format(title), colour=discord.Colour(0xd0021b))

            hand_embed = discord.Embed(title="Next Turn Plan", colour=discord.Colour(0xd0021b))
            return_embed["turn_confirmation"] = hand_embed

            return_embed["hand"] = self.create_hand_embed(fight_data, player_data)
        return return_embed

    def create_hand_embed(self, fight_data, player_data):
        hand = fight_data[player_data]["hand"]
        mana = fight_data[player_data]["mana"]
        health = fight_data[player_data]["current-hp"]
        max_health = fight_data[player_data]["max-hp"]
        emoji_array = ["0⃣", "1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣", "🔟"]
        hand_embed = discord.Embed(title="Your Actions", colour=discord.Colour(0xd0021b),
                                   description="Sequence your next turn! \n"
                                               "You can take up to 3 non-card actions and play as many cards as you want, in any order.\n"
                                               "\nWhen you're done, hit the ✅ button to submit your turn.\n"
                                               "To clear your current plan for the next turn, hit ❌.\n"
                                               "HP: {0}/{1}\nMana: {2}".format(health, max_health, mana),
                                   timestamp=datetime.datetime.now().astimezone(timezone('US/Pacific')))
        hand_embed.add_field(name="-----", value="Your non-card actions (3 per turn)", inline=False)
        self.render_non_card_actions(hand_embed)
        hand_embed.add_field(name="-----", value="Your cards", inline=False)
        hand_embed.add_field(name="Stats", value = "HP: {0}/{1}\nMana: {2}".format(health, max_health, mana), inline=False )

        for z in range(0, len(hand)):
            self.render_compact_card_in_one_embed(hand_embed, hand[z], emoji_array[z])

        hand_embed.set_footer(
            text="Need help? Type `!fg info` for more information.".format(fight_data["round"]))

        return hand_embed

    async def add_controls(self, message, emojis=None):
        if len(message.reactions) > 0:
            message.clear_reactions()
        if emojis is None:
            emojis = ["🔵", "🔴", "⭐", "⬅️", "➡️" ,"0⃣", "1⃣" ,"2⃣", "3⃣","4⃣","5⃣","6⃣","7⃣","8⃣","9⃣", "🔟", "❌", "✅"]
        for emoji in emojis:
            try:
                await message.add_reaction(emoji)
            except Exception as e:
                logging.warning(e)
