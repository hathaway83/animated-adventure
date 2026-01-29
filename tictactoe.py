"""Tic Tac Toe - play against a friend or the computer."""

import os
import random
import time

# ANSI colors and styles
RED = "\033[91m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

TITLE = rf"""{CYAN}{BOLD}
  _____ _        _____            _____
 |_   _(_) ___  |_   _|_ _  ___ |_   _|__   ___
   | | | |/ __|   | |/ _` |/ __|  | |/ _ \ / _ \
   | | | | (__    | | (_| | (__   | | (_) |  __/
   |_| |_|\___|   |_|\__,_|\___|  |_|\___/ \___|
{RESET}"""


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def new_board():
    return [" "] * 9


def colorize(cell, index):
    if cell == "X":
        return f"{RED}{BOLD}X{RESET}"
    if cell == "O":
        return f"{BLUE}{BOLD}O{RESET}"
    return f"{DIM}{index + 1}{RESET}"


def display(board, highlight=None):
    print()
    for row in range(3):
        start = row * 3
        parts = []
        for i in range(start, start + 3):
            cell = colorize(board[i], i)
            if highlight and i in highlight:
                cell = f"{GREEN}{BOLD}{board[i]}{RESET}"
            parts.append(cell)
        print("   " + " | ".join(parts))
        if row < 2:
            print("  -----------")
    print()


def get_move(board, player):
    while True:
        try:
            move = int(input(f"  Player {player}, pick a spot (1-9): ")) - 1
            if 0 <= move <= 8 and board[move] == " ":
                return move
            print("  Invalid move. Try again.")
        except (ValueError, EOFError):
            print("  Enter a number 1-9.")


LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def check_winner(board):
    for a, b, c in LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return None


def get_winning_line(board):
    for a, b, c in LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return [a, b, c]
    return None


# --- AI: Easy (random) ---

def ai_easy(board, ai, human):
    empty = [i for i, c in enumerate(board) if c == " "]
    return random.choice(empty)


# --- AI: Medium (block/win + random) ---

def ai_medium(board, ai, human):
    empty = [i for i, c in enumerate(board) if c == " "]

    for i in empty:
        board[i] = ai
        if check_winner(board) == ai:
            board[i] = " "
            return i
        board[i] = " "

    for i in empty:
        board[i] = human
        if check_winner(board) == human:
            board[i] = " "
            return i
        board[i] = " "

    for pref in [4, 0, 2, 6, 8, 1, 3, 5, 7]:
        if pref in empty:
            return pref

    return empty[0]


# --- AI: Hard (minimax, unbeatable) ---

def minimax(board, is_maximizing, ai, human):
    winner = check_winner(board)
    if winner == ai:
        return 10
    if winner == human:
        return -10
    if " " not in board:
        return 0

    if is_maximizing:
        best = -100
        for i in range(9):
            if board[i] == " ":
                board[i] = ai
                best = max(best, minimax(board, False, ai, human))
                board[i] = " "
        return best
    else:
        best = 100
        for i in range(9):
            if board[i] == " ":
                board[i] = human
                best = min(best, minimax(board, True, ai, human))
                board[i] = " "
        return best


def ai_hard(board, ai, human):
    best_score = -100
    best_move = None
    for i in range(9):
        if board[i] == " ":
            board[i] = ai
            score = minimax(board, False, ai, human)
            board[i] = " "
            if score > best_score:
                best_score = score
                best_move = i
    return best_move


AI_LEVELS = {
    "1": ("Easy", ai_easy),
    "2": ("Medium", ai_medium),
    "3": ("Hard (Unbeatable)", ai_hard),
}


def animate_thinking():
    for char in "thinking", :
        pass
    frames = ["   .  ", "   .. ", "   ..."]
    for frame in frames:
        print(f"\r  Computer is thinking{frame}", end="", flush=True)
        time.sleep(0.3)
    print("\r" + " " * 40 + "\r", end="")


def flash_winner(board, line):
    for _ in range(3):
        clear_screen()
        print(TITLE)
        display(board, highlight=line)
        time.sleep(0.3)
        clear_screen()
        print(TITLE)
        display(board)
        time.sleep(0.2)
    clear_screen()
    print(TITLE)
    display(board, highlight=line)


def scoreboard(scores, vs_ai):
    label_o = "Computer" if vs_ai else "Player O"
    print(f"  {BOLD}{'═' * 38}{RESET}")
    print(f"  {BOLD}  Player X: {scores['X']}  |  {label_o}: {scores['O']}  |  Draws: {scores['draws']}{RESET}")
    print(f"  {BOLD}{'═' * 38}{RESET}")


def play_round(vs_ai, ai_func):
    board = new_board()
    player = "X"
    ai_player = "O" if vs_ai else None

    clear_screen()
    print(TITLE)
    print("  Pick a numbered spot to place your mark.")
    display(board)

    for turn in range(9):
        if vs_ai and player == ai_player:
            animate_thinking()
            move = ai_func(board, ai_player, "X")
        else:
            move = get_move(board, player)

        board[move] = player

        winner = check_winner(board)
        if winner:
            line = get_winning_line(board)
            flash_winner(board, line)
            if vs_ai and winner == ai_player:
                print(f"  {YELLOW}{BOLD}Computer wins!{RESET}")
            else:
                color = RED if winner == "X" else BLUE
                print(f"  {color}{BOLD}Player {winner} wins!{RESET}")
            return winner

        clear_screen()
        print(TITLE)
        remaining = 9 - turn - 1
        print(f"  {DIM}Moves left: {remaining}{RESET}")
        display(board)

        player = "O" if player == "X" else "X"

    clear_screen()
    print(TITLE)
    display(board)
    print(f"  {YELLOW}{BOLD}It's a draw!{RESET}")
    return None


def main():
    scores = {"X": 0, "O": 0, "draws": 0}

    clear_screen()
    print(TITLE)
    print(f"  {BOLD}Game Mode:{RESET}")
    print(f"  1) Play vs Computer")
    print(f"  2) Play vs Friend")
    while True:
        choice = input("\n  Choose mode (1 or 2): ").strip()
        if choice in ("1", "2"):
            break
    vs_ai = choice == "1"

    ai_func = None
    if vs_ai:
        print(f"\n  {BOLD}Difficulty:{RESET}")
        for key, (name, _) in AI_LEVELS.items():
            print(f"  {key}) {name}")
        while True:
            diff = input("\n  Choose difficulty (1-3): ").strip()
            if diff in AI_LEVELS:
                ai_func = AI_LEVELS[diff][1]
                break

    while True:
        winner = play_round(vs_ai, ai_func)
        if winner:
            scores[winner] += 1
        else:
            scores["draws"] += 1

        print()
        scoreboard(scores, vs_ai)

        again = input("\n  Play again? (y/n): ").strip().lower()
        if again != "y":
            print(f"\n  {CYAN}Thanks for playing!{RESET}\n")
            break


if __name__ == "__main__":
    main()
