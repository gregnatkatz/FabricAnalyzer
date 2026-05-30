# ⚽ OG Soccer Smash

A fun, touch-friendly soccer game starring **OG** — a big blue horned monster —
who dribbles and blasts a soccer ball past swarms of little monsters into the goal.
**3 levels**, easy one-finger controls, made to play on an **iPhone**.

![OG](og is the big blue monster ⚽)

## 🎮 How to play

1. **Drag OG** (the big blue monster) around the field with your finger.
2. When OG touches the ball, it **sticks to him** so he can dribble.
3. **Flick** your finger toward the goal and let go to **shoot**! The faster you
   flick, the harder the kick.
4. The **little monsters** chase you and try to steal or kick the ball away —
   OG is big, so you can **body-check** them out of the way.
5. Score enough goals **before the timer runs out** to win the level.

## 🏆 The 3 levels

| Level | Name | Little monsters | Goals to win | Time |
|------:|------|:---------------:|:------------:|:----:|
| 1 | Backyard Kickoff | 3 | 3 | 60s |
| 2 | Monster Park | 5 | 4 | 55s |
| 3 | Stadium Showdown | 7 | 5 | 50s |

Beating a level unlocks the next one (progress is saved on your phone).

## 📱 Play it on your iPhone

The whole game is **one file** (`index.html`) — no app store, no install needed.

**Easiest way (AirDrop / Files):**
1. Get `index.html` onto your iPhone (AirDrop it, email it to yourself, or save
   it to the Files app / iCloud Drive).
2. Tap the file — it opens in Safari and plays instantly.

**Best experience (fullscreen, like a real app):**
1. Open the game in Safari.
2. Tap the **Share** button → **Add to Home Screen**.
3. Launch it from your Home Screen — it runs fullscreen with no browser bars.

**On a computer:** just double-click `index.html`, or run a tiny web server:

```bash
cd og-soccer-game
python3 -m http.server 8000
# then open http://localhost:8000 on your phone (same Wi-Fi) or computer
```

## 🔧 Built with

Plain HTML5 `<canvas>` + JavaScript (no libraries, no build step). Sound effects
are generated with the Web Audio API, so there are **zero asset files** to manage.
Everything lives in `index.html`.

Have fun — go OG! 🦬⚽
