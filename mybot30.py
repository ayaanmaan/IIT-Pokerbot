import random
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionBid
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot
import eval7

class HistoryTracker:
    def __init__(self):
        self.hands_played = 0
        self.opp_vpip = 0
        self.opp_pfr = 0
        
        self.ranked_hands = [
            "AA", "KK", "QQ", "JJ", "AKs", "TT", "AQs", "AKo", "99", "AJs", 
            "KQs", "88", "AQo", "ATs", "KJs", "77", "AJo", "KTs", "QJs", "66", 
            "ATo", "A9s", "KTo", "KQo", "QTs", "A8s", "KJo", "JTs", "55", "A7s", 
            "A9o", "K9s", "QJo", "A5s", "A6s", "44", "A4s", "A8o", "K8s", "QTo", 
            "A3s", "K9o", "A2s", "J9s", "A7o", "T9s", "33", "Q9s", "K7s", "JTo", 
            "A5o", "K6s", "A6o", "22", "K5s", "K8o", "A4o", "K4s", "Q8s", "A3o", 
            "T8s", "K3s", "K7o", "A2o", "Q9o", "J8s", "K2s", "98s", "K6o", "Q7s", 
            "J9o", "K5o", "T9o", "Q6s", "Q8o", "K4o", "87s", "Q5s", "J7s", "K3o", 
            "T7s", "Q4s", "K2o", "97s", "Q7o", "Q3s", "J8o", "T8o", "86s", "Q2s", 
            "98o", "J6s", "76s", "Q6o", "T6s", "J5s", "96s", "Q5o", "J7o", "87o", 
            "85s", "J4s", "T7o", "Q4o", "75s", "97o", "J3s", "65s", "Q3o", "T5s", 
            "J2s", "86o", "95s", "Q2o", "76o", "T4s", "64s", "J6o", "54s", "84s", 
            "T6o", "96o", "T3s", "74s", "J5o", "85o", "T2s", "94s", "65o", "75o", 
            "J4o", "53s", "93s", "83s", "63s", "J3o", "95o", "43s", "73s", "T5o", 
            "J2o", "92s", "82s", "54o", "64o", "T4o", "52s", "74o", "42s", "T3o", 
            "84o", "94o", "62s", "32s", "T2o", "72s", "53o", "83o", "93o", "63o", 
            "43o", "92o", "73o", "82o", "52o", "62o", "42o", "72o", "32o"
        ]

    def update_preflop(self, opp_action: str):
        self.hands_played += 1
        if opp_action in ['call', 'raise']:
            self.opp_vpip += 1
        if opp_action == 'raise':
            self.opp_pfr += 1

    def get_pfr_percent(self):
        if self.hands_played < 5: return 0.35 
        return max(0.15, self.opp_pfr / max(1, self.hands_played))
        
    def get_vpip_percent(self):
        if self.hands_played < 5: return 0.70
        return max(0.40, self.opp_vpip / max(1, self.hands_played))

    def get_opponent_range(self, action_faced: str):
        percentile = self.get_pfr_percent() if action_faced == 'raise' else self.get_vpip_percent()
        percentile = max(0.02, min(percentile, 0.95)) 
        slice_index = min(int(169 * percentile), 169)
        return self.ranked_hands[:slice_index]

class Player(BaseBot):
    def __init__(self) -> None:
        super().__init__()
        self.history = HistoryTracker()
        self.bb_size = 20  
        self.sb_size = 10
        
    def _get_combos_from_range(self, range_list):
        suits, combos = 'shdc', []
        for hand in range_list:
            r1, r2 = hand[0], hand[1]
            if len(hand) == 2:
                for i in range(4):
                    for j in range(i + 1, 4): combos.append((r1 + suits[i], r2 + suits[j]))
            elif hand[2] == 's':
                for s in suits: combos.append((r1 + s, r2 + s))
            elif hand[2] == 'o':
                for s1 in suits:
                    for s2 in suits:
                        if s1 != s2: combos.append((r1 + s1, r2 + s2))
        return combos
    
    def on_hand_start(self, game_info: GameInfo, current_state: PokerState) -> None:
        self.preflop_aggressor = False
        self.raises_this_street = 0
        self.opp_action_this_hand = 'fold'

    def on_hand_end(self, game_info: GameInfo, current_state: PokerState) -> None:
        self.history.update_preflop(self.opp_action_this_hand)

    def _get_preflop_percentile(self, my_cards):
        ranks = "23456789TJQKA"
        r1, s1 = my_cards[0][0], my_cards[0][1]
        r2, s2 = my_cards[1][0], my_cards[1][1]
        if ranks.find(r1) < ranks.find(r2):
            r1, r2 = r2, r1
        suit_str = 's' if s1 == s2 else 'o'
        if r1 == r2: suit_str = ''
        
        hand_str = r1 + r2 + suit_str
        try:
            return self.history.ranked_hands.index(hand_str) / 169.0
        except ValueError:
            return 1.0

    def _get_danger_level(self, board, my_cards, hand_type):
        if len(board) < 3: return 0
        
        b_suits = [c[1] for c in board]
        b_ranks = [c[0] for c in board]
        is_flush_board = any(b_suits.count(s) >= 3 for s in set(b_suits))
        is_paired_board = len(set(b_ranks)) < len(b_ranks)
        ranks_str = "23456789TJQKA"
        indices = [ranks_str.find(r) for r in set(b_ranks)]
        if 12 in indices: indices.append(-1)
        indices.sort()
        
        is_straight_board = False
        for i in range(len(indices) - 2):
            if indices[i+2] - indices[i] <= 4:
                is_straight_board = True
                break

        hand_ranks = ['High Card', 'Pair', 'Two Pair', 'Three of a Kind', 'Straight', 'Flush', 'Full House', 'Four of a Kind', 'Straight Flush']
        try:
            my_idx = hand_ranks.index(hand_type)
        except ValueError:
            my_idx = 0
            
        danger = 0
        if is_flush_board and my_idx < hand_ranks.index('Flush'): danger += 1
        if is_paired_board and my_idx < hand_ranks.index('Full House'): danger += 1
        if is_straight_board and my_idx < hand_ranks.index('Straight'): danger += 1
                
        return danger

    def _safe_raise(self, target_amount, min_r, max_r, current_state):
        if current_state.can_act(ActionRaise):
            return ActionRaise(max(min_r, min(int(target_amount), max_r)))
        return ActionCall() if current_state.can_act(ActionCall) else ActionCheck()

    def _simulate_equity(self, my_cards, board, opp_revealed, action_faced, opp_shows_strength=False, iterations=1000):
        hero = [eval7.Card(c) for c in my_cards]
        brd = [eval7.Card(c) for c in board]
        dead = my_cards + board
        
        abstract = self.history.get_opponent_range(action_faced)
        all_combos = self._get_combos_from_range(abstract)
        
        valid_opp = []
        for c in all_combos:
            if c[0] in dead or c[1] in dead: continue
            if opp_revealed and opp_revealed[0] not in c: continue
            valid_opp.append([eval7.Card(c[0]), eval7.Card(c[1])])
        if opp_shows_strength and len(brd) >= 3 and valid_opp:
            scored_combos = [(c, eval7.evaluate(c + brd)) for c in valid_opp]
            scored_combos.sort(key=lambda x: x[1], reverse=True)
            keep_count = max(1, int(len(scored_combos) * 0.25))
            valid_opp = [x[0] for x in scored_combos[:keep_count]]

        use_random = len(valid_opp) == 0
        deck_strs = [r+s for r in "23456789TJQKA" for s in "cdhs"]
        for c in dead:
            if c in deck_strs: deck_strs.remove(c)
        if opp_revealed and use_random and opp_revealed[0] in deck_strs:
            deck_strs.remove(opp_revealed[0])
            
        deck = [eval7.Card(c) for c in deck_strs]
        wins, ties, needed = 0, 0, 5 - len(board)
        
        for _ in range(iterations):
            opp_needed = 2 - (1 if opp_revealed and use_random else 0) if use_random else 0
            drawn = random.sample(deck, needed + opp_needed)
            sim_brd = brd + drawn[:needed]
            
            if use_random:
                sim_opp = ([eval7.Card(opp_revealed[0])] if opp_revealed else []) + drawn[needed:]
            else:
                sim_opp = random.choice(valid_opp)
                
            h_s = eval7.evaluate(hero + sim_brd)
            o_s = eval7.evaluate(sim_opp + sim_brd)
            
            if h_s > o_s: wins += 1
            elif h_s == o_s: ties += 1
                
        return (wins + 0.5 * ties) / iterations

    def get_move(self, game_info: GameInfo, current_state: PokerState) -> ActionFold | ActionCall | ActionCheck | ActionRaise | ActionBid:
        street = current_state.street
        my_cards = current_state.my_hand
        board = getattr(current_state, 'board', [])
        pot = getattr(current_state, 'pot', 0)
        my_chips = getattr(current_state, 'my_chips', 5000)
        opp_revealed = current_state.opp_revealed_cards
        min_raise, max_raise = current_state.raise_bounds if hasattr(current_state, 'raise_bounds') and current_state.raise_bounds else (0, 0)
        cost_to_call = getattr(current_state, 'cost_to_call', 0)

        if street == 'auction':
            equity = self._simulate_equity(my_cards, board, [], self.opp_action_this_hand)
            if equity < 0.25: return ActionBid(0)
            if equity > 0.85: return ActionBid(random.choice([2, 3, 5]))
            target = int(pot * random.uniform(0.30, 0.75))
            return ActionBid(min(target, my_chips))

        if street == 'pre-flop':
            if cost_to_call > self.bb_size: self.opp_action_this_hand = 'raise'
            elif cost_to_call == 0 and current_state.is_bb: self.opp_action_this_hand = 'call'
            
            percentile = self._get_preflop_percentile(my_cards)
            
            if cost_to_call < self.bb_size:
                if percentile <= 0.65:
                    self.preflop_aggressor = True
                    return self._safe_raise(2.5 * self.bb_size, min_raise, max_raise, current_state)
                return ActionFold() if current_state.can_act(ActionFold) else ActionCheck()

            elif cost_to_call >= self.bb_size:
                self.raises_this_street += 1
                if self.raises_this_street >= 2:
                    if percentile <= 0.05: return self._safe_raise(max_raise, min_raise, max_raise, current_state) 
                    return ActionFold() if current_state.can_act(ActionFold) else ActionCheck()
                    
                if percentile <= 0.15:
                    self.preflop_aggressor = True
                    return self._safe_raise(cost_to_call * 3, min_raise, max_raise, current_state)
                elif percentile <= 0.45:
                    return ActionCall() if current_state.can_act(ActionCall) else ActionCheck()
                return ActionFold() if current_state.can_act(ActionFold) else ActionCheck()
        opp_shows_strength = cost_to_call > (pot * 0.40)
        equity = self._simulate_equity(my_cards, board, opp_revealed, self.opp_action_this_hand, opp_shows_strength)
        
        if not opp_revealed: 
            equity -= 0.10 
        
        my_eval_cards = [eval7.Card(c) for c in my_cards + board]
        hand_val = eval7.evaluate(my_eval_cards)
        hand_type = eval7.handtype(hand_val)
        danger_level = self._get_danger_level(board, my_cards, hand_type)
        equity -= (0.15 * danger_level)

        req_equity = cost_to_call / (pot + cost_to_call) if (pot + cost_to_call) > 0 else 0
        bet_size_ratio = cost_to_call / pot if pot > 0 else 0
        if cost_to_call > 0:
            if street == 'river' and hand_type == 'High Card':
                return ActionFold() if current_state.can_act(ActionFold) else ActionCheck()
            if bet_size_ratio >= 1.0 and danger_level >= 1:
                return ActionFold() if current_state.can_act(ActionFold) else ActionCheck()

            if equity > req_equity + 0.20: 
                return self._safe_raise(pot * 0.70, min_raise, max_raise, current_state) 
            elif equity >= req_equity + 0.05:
                return ActionCall() if current_state.can_act(ActionCall) else ActionCheck()
            else:
                return ActionFold() if current_state.can_act(ActionFold) else ActionCheck()

        if current_state.can_act(ActionRaise) or current_state.can_act(ActionCheck):
            if equity > 0.70:
                return self._safe_raise(pot * 0.70, min_raise, max_raise, current_state)
            elif 0.55 < equity <= 0.70:
                return self._safe_raise(pot * 0.50, min_raise, max_raise, current_state)
                
            bet_fraction = 0.75 
            optimal_bluff_freq = bet_fraction / (1.0 + 2.0 * bet_fraction) 
            
            if 0.40 <= equity <= 0.55:
                if random.random() < (optimal_bluff_freq * 1.5):
                    return self._safe_raise(pot * bet_fraction, min_raise, max_raise, current_state)
            elif equity < 0.40:
                if opp_revealed and "2345678".find(opp_revealed[0][0]) != -1:
                    if random.random() < 0.80: 
                        return self._safe_raise(pot * 0.85, min_raise, max_raise, current_state)
                if random.random() < optimal_bluff_freq:
                    return self._safe_raise(pot * bet_fraction, min_raise, max_raise, current_state)
            
            return ActionCheck()

        return ActionCall() if current_state.can_act(ActionCall) else ActionFold()

if __name__ == '__main__':
    run_bot(Player(), parse_args())