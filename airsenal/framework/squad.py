"""
The class for an FPL squad.
Contains a set of players.
Is able to check that it obeys all constraints.
"""
from operator import itemgetter
import numpy as np

from airsenal.framework.player import CandidatePlayer, Player
from airsenal.framework.utils import get_player, NEXT_GAMEWEEK, CURRENT_SEASON, fetcher

# how many players do we need to add
TOTAL_PER_POSITION = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}

# min/max active players per position
ACTIVE_PER_POSITION = {"GK": (1, 1), "DEF": (3, 5), "MID": (3, 5), "FWD": (1, 3)}

FORMATIONS = [
    (3, 4, 3),
    (3, 5, 2),
    (4, 3, 3),
    (4, 4, 2),
    (4, 5, 1),
    (5, 4, 1),
    (5, 3, 2),
]


class Squad(object):
    """
    Squad class.  Contains 15 players
    """

    def __init__(self, budget=1000):
        """
        constructor - start with an initial empty player list,
        and £100M
        """
        self.players = []
        self.budget = budget
        self.num_position = {"GK": 0, "DEF": 0, "MID": 0, "FWD": 0}
        self.free_subs = 0
        self.subs_this_week = 0
        self.verbose = False

    def __repr__(self):
        """
        Display the squad
        """
        print("\n=== starting 11 ===\n")
        for position in ["GK", "DEF", "MID", "FWD"]:
            print("\n== {} ==\n".format(position))
            for p in self.players:
                if p.position == position and p.is_starting:
                    player_line = "{} ({})".format(p.name, p.team)
                    if p.is_captain:
                        player_line += "(C)"
                    elif p.is_vice_captain:
                        player_line += "(VC)"
                    print(player_line)
        print("\n=== subs ===\n")

        subs = [p for p in self.players if not p.is_starting]
        subs.sort(key=lambda p: p.sub_position)
        for p in subs:
            print("{} ({})".format(p.name, p.team))
        return ""

    def is_complete(self):
        """
        See if we have 15 players.
        """
        num_players = sum(self.num_position.values())
        return num_players == 15

    def add_player(
        self,
        p,
        price=None,
        season=CURRENT_SEASON,
        gameweek=NEXT_GAMEWEEK,
        check_budget=True,
        check_team=True,
        dbsession=None,
    ):
        """
        Add a player.  Can do it by name or by player_id.
        If no price is specified, CandidatePlayer constructor will use the
        current price as found in DB, but if one is specified, we override
        with that value.
        """
        if isinstance(p, int) or isinstance(p, str) or isinstance(p, Player):
            player = CandidatePlayer(p, season, gameweek, dbsession=dbsession)
        else:  # already a CandidatePlayer (or an equivalent test class)
            player = p
        # set the price if one was specified.
        if price:
            player.purchase_price = price
        # check if constraints are met
        if not self.check_no_duplicate_player(player):
            if self.verbose:
                print("Already have {} in team".format(player.name))
            return False
        if not self.check_num_in_position(player):
            if self.verbose:
                print(
                    "Unable to add player {} - too many {}".format(
                        player.name, player.position
                    )
                )
            return False
        if check_budget and not self.check_cost(player):
            if self.verbose:
                print("Cannot afford player {}".format(player.name))
            return False
        if check_team and not self.check_num_per_team(player):
            if self.verbose:
                print(
                    "Cannot add {} - too many players from {}".format(
                        player.name, player.team
                    )
                )
            return False
        self.players.append(player)
        self.num_position[player.position] += 1
        self.budget -= player.purchase_price
        return True

    def remove_player(
        self,
        player_id,
        price=None,
        season=CURRENT_SEASON,
        gameweek=NEXT_GAMEWEEK,
        use_api=False,
        dbsession=None,
    ):
        """
        Remove player from our list.
        If a price is specified, we use that, otherwise we
        calculate the player's sale price based on his price in the
        team vs. his current price in the API (or if the API fails
        or use_api is False, the current price for that player in the database.)
        """
        for p in self.players:
            if p.player_id == player_id:
                if price:
                    self.budget += price
                else:
                    self.budget += self.get_sell_price_for_player(
                        p,
                        use_api=use_api,
                        season=season,
                        gameweek=gameweek,
                        dbsession=dbsession,
                    )
                self.num_position[p.position] -= 1
                self.players.remove(p)
                return True
        return False

    def get_sell_price_for_player(
        self,
        player,
        use_api=False,
        season=CURRENT_SEASON,
        gameweek=NEXT_GAMEWEEK,
        dbsession=None,
    ):
        """Get sale price for player (a player in self.players) in the current
        gameweek of the current season.
        """
        price_bought = player.purchase_price
        player_id = player.player_id
        price_now = None
        if use_api and season == CURRENT_SEASON and gameweek >= NEXT_GAMEWEEK:
            try:
                # first try getting the price for the player from the API
                player_db = get_player(player_id)
                price_now = fetcher.get_player_summary_data()[player_db.fpl_api_id][
                    "now_cost"
                ]
            except:
                pass

        if not price_now:
            player_db = get_player(player_id, dbsession=dbsession)

            if player_db:
                price_now = player_db.price(season, gameweek)
        if not price_now:
            # if all else fails just use the purchase price as the sale
            # price for this player.
            print(
                "Using purchase price as sale price for",
                player.player_id,
                player.name,
            )
            price_now = price_bought

        if price_now > price_bought:
            price_sell = (price_now + price_bought) // 2
        else:
            price_sell = price_now
        return price_sell

    def check_no_duplicate_player(self, player):
        """
        Check we don't already have the player.
        """
        for p in self.players:
            if p.player_id == player.player_id:
                return False
        return True

    def check_num_in_position(self, player):
        """
        check we have fewer than the limit of
        num players in the chosen players position.
        """
        position = player.position
        return self.num_position[position] < TOTAL_PER_POSITION[position]

    def check_num_per_team(self, player):
        """
        check we have fewer than 3 players from the same
        team as the specified player.
        """
        num_same_team = 0
        new_player_team = player.team
        for p in self.players:
            if p.team == new_player_team:
                num_same_team += 1
                if num_same_team == 3:
                    return False
        return True

    def check_cost(self, player):
        """
        check we can afford the player.
        """
        can_afford = player.purchase_price <= self.budget
        return can_afford

    def _calc_expected_points(self, tag):
        """
        estimate the expected points for the specified gameweek.
        If no gameweek is specified, it will be the next fixture
        """
        for p in self.players:
            p.calc_predicted_points(tag)
        pass

    def optimize_subs(self, gameweek, tag):
        """
        based on pre-calculated expected points,
        choose the best starting 11, obeying constraints.
        """
        # first order all the players by expected points
        player_dict = {"GK": [], "DEF": [], "MID": [], "FWD": []}
        for p in self.players:
            try:
                points_prediction = p.predicted_points[tag][gameweek]

            except (KeyError):
                ## player does not have a game in this gameweek
                points_prediction = 0
            player_dict[p.position].append((p, points_prediction))
        for v in player_dict.values():
            v.sort(key=itemgetter(1), reverse=True)

        # always start the first-placed and sub the second-placed keeper
        player_dict["GK"][0][0].is_starting = True
        player_dict["GK"][1][0].is_starting = False
        best_score = 0.0
        best_formation = None
        for f in FORMATIONS:
            self.apply_formation(player_dict, f)
            score = self.total_points_for_starting_11(gameweek, tag)
            if score >= best_score:
                best_score = score
                best_formation = f
        if self.verbose:
            print("Best formation is {}".format(best_formation))
        self.apply_formation(player_dict, best_formation)
        self.order_substitutes(gameweek, tag)

        return best_score

    def order_substitutes(self, gameweek, tag):
        # order substitutes by expected points (descending)
        subs = [p for p in self.players if not p.is_starting]

        points = []
        for player in subs:
            try:
                points.append(player.predicted_points[tag][gameweek])
            except ValueError:
                points.append(0)

        # sort the players by points (descending)
        ordered_sub_inds = reversed(np.argsort(points))
        for sub_position, sub_ind in enumerate(ordered_sub_inds):
            subs[sub_ind].sub_position = sub_position

    def apply_formation(self, player_dict, formation):
        """
        set players' is_starting to True or False
        depending on specified formation in format e.g.
        (4,4,2)
        """
        for i, pos in enumerate(["DEF", "MID", "FWD"]):
            for index, player in enumerate(player_dict[pos]):
                if index < formation[i]:
                    player[0].is_starting = True
                else:
                    player[0].is_starting = False

    def total_points_for_starting_11(self, gameweek, tag, triple_captain=False):
        """
        simple sum over starting players
        """
        total = 0.0
        for player in self.players:
            if player.is_starting:
                total += player.predicted_points[tag][gameweek]
                if player.is_captain:
                    total += player.predicted_points[tag][gameweek]
                    if triple_captain:
                        total += player.predicted_points[tag][gameweek]

        return total

    def total_points_for_subs(
        self, gameweek, tag, sub_weights={"GK": 1, "Outfield": (1, 1, 1)}
    ):

        outfield_subs = [
            p for p in self.players if (not p.is_starting) and (p.position != "GK")
        ]
        outfield_subs = sorted(outfield_subs, key=lambda p: p.sub_position)

        gk_sub = [
            p for p in self.players if (not p.is_starting) and (p.position == "GK")
        ][0]

        total = sub_weights["GK"] * gk_sub.predicted_points[tag][gameweek]

        for i, player in enumerate(outfield_subs):
            total += sub_weights["Outfield"][i] * player.predicted_points[tag][gameweek]

        return total

    def get_expected_points(
        self, gameweek, tag, bench_boost=False, triple_captain=False
    ):
        """
        expected points for the starting 11.
        """
        if not self.is_complete():
            raise RuntimeError("Squad is incomplete")
        self._calc_expected_points(tag)

        self.optimize_subs(gameweek, tag)
        self.pick_captains(gameweek, tag)

        total_score = self.total_points_for_starting_11(
            gameweek, tag, triple_captain=triple_captain
        )

        if bench_boost:
            total_score += self.total_points_for_subs(gameweek, tag)

        return total_score

    def pick_captains(self, gameweek, tag):
        """
        pick the highest two expected points for captain and vice-captain
        """
        player_list = []
        for p in self.players:
            p.is_captain = False
            p.is_vice_captain = False
            player_list.append((p, p.predicted_points[tag][gameweek]))

        player_list.sort(key=itemgetter(1), reverse=True)
        player_list[0][0].is_captain = True
        player_list[1][0].is_vice_captain = True
