"""Tic Tac Toe - two player command-line game."""


def new_board():
    return [" "] * 9


def display(board):
    for row in range(3):
        cells = board[row * 3 : row * 3 + 3]
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


def check_winner(board):
    lines = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
        (0, 3, 6), (1, 4, 7), (2, 5, 8),  # cols
        (0, 4, 8), (2, 4, 6),              # diagonals
    ]
    for a, b, c in lines:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return None


def main():
    board = new_board()
    player = "X"

    print("Tic Tac Toe")
    print("Positions are numbered 1-9, left to right, top to bottom.\n")
    display(board)

    for turn in range(9):
        move = get_move(board, player)
        board[move] = player
        display(board)

        winner = check_winner(board)
        if winner:
            print(f"Player {winner} wins!")
            return

        player = "O" if player == "X" else "X"

    print("It's a draw!")


if __name__ == "__main__":
    main()
