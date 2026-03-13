# Q-Less

An interactive browser-based version of the Q-Less crossword solitaire game.

Roll 12 dice, drag the letters onto the board, and arrange them into connected words — like a crossword. Use every single tile to win.

## How to play

- Hit **Roll dice** to get your 12 letters
- Drag tiles from the tray onto the grid to build words
- Words must be **3 or more letters**
- All tiles must form **one connected group** (like a crossword — no floating islands)
- No proper nouns
- Hit **Check words** once all 12 tiles are on the board
- Valid words turn green, invalid ones turn red
- Use **Clear board** to sweep everything back to the tray, or **Reroll** for a fresh set of letters

## Running locally

Because the word list is fetched as a local file, you'll need to serve the project over HTTP rather than opening `index.html` directly.

The easiest options:

**VS Code Live Server** — install the Live Server extension, right-click `index.html`, and choose "Open with Live Server".

**Python** — in the project folder, run:
```
python -m http.server
```
Then open `http://localhost:8000` in your browser.

**GitHub Pages** — push to a repository with Pages enabled and it works automatically.

## Setup

1. Clone or download this repository
2. Download the SOWPODS word list from [jesstess/Scrabble](https://github.com/jesstess/Scrabble) — the file is `sowpods.txt`
3. Rename it to `words.txt` and place it in the same folder as `index.html`
4. Serve locally or push to GitHub Pages

## Word list

This project uses the **SOWPODS** word list — the international Scrabble tournament dictionary, containing approximately 270,000 words.

Word list sourced from [jesstess/Scrabble](https://github.com/jesstess/Scrabble) — thank you!

## Inspired by

The original [Q-Less](https://qlessgame.com) dice game by Tom Sturdevant. This is an unofficial fan-made implementation. Please support the original!

## Built with

Plain HTML, CSS, and JavaScript.