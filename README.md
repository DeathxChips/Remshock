# Remshock

An action bullet hell game.
A game inspired by Cuphead boss fights and a characters from Deadlock. It's a simple run-and-gun platformer with 3 hearts, a formidable boss, and equally dangerous bullets!


This project is written completely in Python using the Pygame library.

## Controls

* **Move left / right:** `A` / `D` or `Left Arrow` / `Right Arrow`
* **Jump:** `Space`, `W`, or `Up Arrow`
* **Dash (with brief invulnerability):** `Shift` or `K`
* **Shoot:** `X` or `J`
* **Restart (after win or game over):** `R`
* **Quit:** `Esc`

## Gameplay & Features

* **3-phase boss fight (THE VISCOUS):** attack patterns (`slam`, `spread`, `rain`) speed up and scale across phases as the boss loses HP.
* **Player health & invulnerability:** 3 hearts (`HP`) with brief invulnerability frames after taking damage or dashing.
* **Custom pixel art & tilesets:** pixel-scaled sprites, ground tileset support, and screen shake / particle effects.

## How to Run

1. Make sure **Python** and **Pygame** are installed:
   ```bash
   pip install pygame
