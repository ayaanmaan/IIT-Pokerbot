import re
import statistics

class PokerLogParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.bot_payoffs = {}  # Tracks all round-by-round chip changes
        self.bot_bids = {}     # Tracks all auction bids
        self.auction_wins = {} # Tracks how many auctions each bot won
        self.rounds_played = 0

    def parse(self):
        # Regex patterns to catch the essential log events
        round_pattern = re.compile(r'^Round #(\d+)')
        award_pattern = re.compile(r'^(\w+) awarded (-?\d+)')
        bid_pattern = re.compile(r'^(\w+) bids (\d+)')
        auction_win_pattern = re.compile(r'^(\w+) won the auction')

        with open(self.file_path, 'r') as file:
            for line in file:
                line = line.strip()
                
                # Count total rounds
                if round_pattern.match(line):
                    self.rounds_played += 1

                # Capture Payoffs (Bankroll changes)
                award_match = award_pattern.match(line)
                if award_match:
                    bot, amount = award_match.groups()
                    amount = int(amount)
                    if bot not in self.bot_payoffs:
                        self.bot_payoffs[bot] = []
                    self.bot_payoffs[bot].append(amount)
                    
                # Capture Auction Bids
                bid_match = bid_pattern.match(line)
                if bid_match:
                    bot, amount = bid_match.groups()
                    amount = int(amount)
                    if bot not in self.bot_bids:
                        self.bot_bids[bot] = []
                    self.bot_bids[bot].append(amount)

                # Capture Auction Wins
                auction_win_match = auction_win_pattern.match(line)
                if auction_win_match:
                    bot = auction_win_match.group(1)
                    if bot not in self.auction_wins:
                        self.auction_wins[bot] = 0
                    self.auction_wins[bot] += 1

    def get_stats(self, bot_name):
        payoffs = self.bot_payoffs.get(bot_name, [])
        bids = self.bot_bids.get(bot_name, [])
        auctions_won = self.auction_wins.get(bot_name, 0)
        
        if not payoffs:
            return None
        
        winning_rounds = [p for p in payoffs if p > 0]
        
        stats = {
            "Total Bankroll": sum(payoffs),
            "Win Rate (%)": (len(winning_rounds) / len(payoffs)) * 100,
            "Max Win": max(payoffs),
            "Max Loss": min(payoffs),
            "Mean Payoff": statistics.mean(payoffs),
            "Payoff Variance": statistics.variance(payoffs) if len(payoffs) > 1 else 0,
            "Mean Auction Bid": statistics.mean(bids) if bids else 0,
            "Bid Variance": statistics.variance(bids) if len(bids) > 1 else 0,
            "Auction Win Rate (%)": (auctions_won / self.rounds_played) * 100 if self.rounds_played else 0
        }
        return stats

    def generate_report(self):
        self.parse()
        print(f"=== PARSED {self.rounds_played} ROUNDS ===")
        for bot in self.bot_payoffs.keys():
            stats = self.get_stats(bot)
            if not stats: continue
            
            print(f"\nStats for {bot}:")
            print("-" * 30)
            print(f"  Total Bankroll:  {stats['Total Bankroll']}")
            print(f"  Win Rate:        {stats['Win Rate (%)']:.1f}%")
            print(f"  Mean Payoff:     {stats['Mean Payoff']:.2f}")
            print(f"  Payoff Variance: {stats['Payoff Variance']:.2f}")
            print(f"  Max Win (Hand):  {stats['Max Win']}")
            print(f"  Max Loss (Hand): {stats['Max Loss']}")
            print("-" * 30)
            print(f"  Auction Win Rate: {stats['Auction Win Rate (%)']:.1f}%")
            print(f"  Mean Bid Amount:  {stats['Mean Auction Bid']:.2f}")
            print(f"  Bid Variance:     {stats['Bid Variance']:.2f}")

if __name__ == "__main__":
    try:
        locstr = "logs\\sgdg_1\\ff25ffa5-e567-4bca-b7c3-f2609c258abb.glog"
        parser = PokerLogParser(locstr)
        parser.generate_report()
    except FileNotFoundError:
        print("Please ensure 'game_log.txt' exists in the directory.")