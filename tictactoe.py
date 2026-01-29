"""Tic Tac Toe - play against a friend or the computer."""

import random
import os

# ANSI colors
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


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


def display(board):
    for row in range(3):
        start = row * 3
        cells = [colorize(board[i], i) for i in range(start, start + 3)]
        print(" " + " | ".join(cells))
        if row < 2:
            print("-----------")
    print()


def get_move(board, player):
    while True:
        try:
            move = int(input(f"Player {player}, pick a spot (1-9): ")) - 1
            if 0 <= move <= 8 and board[move] == " ":
                return move
            print("Invalid move. Try again.")
        except (ValueError, EOFError):
            print("Enter a number 1-9.")


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


def ai_move(board, ai, human):
    empty = [i for i, c in enumerate(board, ) if c == " "]

    # Win if possible
    for i in empty:
        board[i] = ai
        if check_winner(board) == ai:
            board[i] = " "
            return i
        board[i] = " "

    # Block opponent's win
    for i in empty:
        board[i] = human
        if check_winner(board) == human:
            board[i] = " "
            return i
        board[i] = " "

    # Take center, then corners, then whatever's left
    for pref in [4, 0, 2, 6, 8, 1, 3, 5, 7]:
        if pref in empty:
            return pref

    return empty[0]


def play_round(vs_ai):
    board = new_board()
    player = "X"
    ai_player = "O" if vs_ai else None

    clear_screen()
    print(f"{BOLD}Tic Tac Toe{RESET}")
    print("Pick a numbered spot to place your mark.\n")
    display(board)

    for _ in range(9):
        if vs_ai and player == ai_player:
            move = ai_move(board, ai_player, "X")
            print(f"Computer plays {move + 1}")
        else:
            move = get_move(board, player)

        board[move] = player
        clear_screen()
        print(f"{BOLD}Tic Tac Toe{RESET}\n")
        display(board)

        winner = check_winner(board)
        if winner:
            if vs_ai and winner == ai_player:
                print("Computer wins!")
            else:
                print(f"{BOLD}Player {winner} wins!{RESET}")
            return winner

        player = "O" if player == "X" else "X"

    print("It's a draw!")
    return None


def main():
    scores = {"X": 0, "O": 0, "draws": 0}

    clear_screen()
    print(f"{BOLD}Tic Tac Toe{RESET}\n")
    print("1) Play vs Computer")
    print("2) Play vs Friend")
    while True:
        choice = input("\nChoose mode (1 or 2): ").strip()
        if choice in ("1", "2"):
            break
    vs_ai = choice == "1"

    while True:
        winner = play_round(vs_ai)
        if winner:
            scores[winner] += 1
        else:
            scores["draws"] += 1

        label_o = "Computer" if vs_ai else "Player O"
        print(f"\n{BOLD}Score:{RESET}  Player X: {scores['X']}  |  {label_o}: {scores['O']}  |  Draws: {scores['draws']}")

        again = input("\nPlay again? (y/n): ").strip().lower()
        if again != "y":
            print("Thanks for playing!")
            break


if __name__ == "__main__":
    main()
