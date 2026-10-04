# Process

## Tools

AI assistants wrote most of the code in this repository, in two rounds: one chat explored the subject with me and iterated the picture until it looked right; a second reworked the animation for speed and built the web page. Everything ran with `uv run` — matplotlib draws, Pillow assembles the GIF and squeezes the WebP the page plays, GitHub Actions deploys the site on every push. What stayed mine: choosing the phenomenon, setting the rules the picture had to obey,and judging the results on screen.

## What I had to correct

- **The hourly circle.** The first drafts arranged 8,760 hourly rays around 360°. The lines folded into a smudge, and the AI kept offering thinner lines. The problem was overlap, not thickness — no thickness fixes lines printed on top of each other. One bar per day ended it.
- **The transition style.** Early animations let one year fade out and the next fade in, which throws away the whole point of comparing years. I set the rules instead: every day's bar grows or shrinks continuously at its own fixed angle, all twenty-six years share one fixed scale and one fixed legend, and 29 February must never shift the calendar. The easing curve was the AI's; the rules were mine.
- **The eight-second claim.** After the speed rewrite the assistant reported the animation rendering in about eight seconds; my own run took over a minute. The code was fine — I was still running the old file. Replacing the file properly and timing it myself was the fix, and it is why I now always check which file I am actually running.
- **The laggy GIF on GitHub.** The animation stuttered in the browser, which has to pull a 60 MB file and decode 326 full-size frames before it can play smoothly. The fix was a different venue: a page of its own, rebuilt on every push, that plays the animation straight from the repository.

## Kept

The vectorised animation rewrite. A single frame used to issue 623 `ax.bar()` calls; the rewrite draws a whole year as three `PolyCollection`s, renders straight from the drawing buffer instead of writing PNGs to disk, and renders frames in parallel across the CPU cores. I kept it because it is about ten times faster — 82 seconds down to 8 — and because a pixel-level comparison of the old and new builds, which the assistant ran, found them identical apart from anti-aliased edges. That speed is what made it practical to commit the full-resolution animation and serve it from the repository.

## Rejected

The twenty-six-line overlay: one polyline per year, stacked on the same axes to hunt for a pattern. It is a legitimate chart and the AI produced it quickly, but it was not this piece — daily noise shredded the lines, nothing read as a pulse, and it abandoned the circle the project is built on. I dropped it after one look and went back to one circle that morphs.
