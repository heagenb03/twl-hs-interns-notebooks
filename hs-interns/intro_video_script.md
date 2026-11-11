# Week 1 Intro Video — Script

**Target length:** 8:00–9:00 (time a read-aloud before recording — Part 2 is the
fat if you need to cut)
**Format:** Camera for Parts 1, 2, 4. Screen recording for Part 3.
**Tone:** Talking to a smart 16-year-old who is good at reading and has never
written a line of code. Not a lecture. No apologizing for the material.

**Do not:** show any notebook output, run any beat, or reveal a result. The wow
moments are theirs. This video sells and de-risks; it does not teach.

---

## Part 1 — Who I am, what this is (0:00–1:00)

[CAMERA]

> Hey — I'm Heagen. You're all interning with the Trade War Lab for the next two
> weeks, and this is the only video I'm going to make you watch. Under ten
> minutes, then you're off.
>
> Here's the shape of it. Week one, you're going to run some real analysis on
> real US-China policy data, and you're going to do it in Python, which most of
> you have never written. That's fine. I'll explain why in a second.
>
> Week two, you're going to do work the lab actually needs — and I mean that
> literally, not in a "here's a nice project for the intern" way.

**[On-screen text: "Week 1 notebook done by Friday [DATE]. Plan for ~2 hours."]**

> And two logistics up front, because I don't want anyone guessing.
>
> Your notebook has three main sections. Realistically that's about two hours of
> actual work — it is not a thing you need to give up a weekend for. And I'd like
> it worked through by **Friday, [DATE]**. If you get there early, great, there's
> extra stuff at the bottom of every notebook to keep going with.

---

## Part 2 — Why you, and what a model actually is (0:45–3:00)

[CAMERA]

> First thing I want to get out of the way, because I think some of you are
> already worried about it: you were not picked in spite of being humanities
> people. You were picked because of it.
>
> Here's what the lab does. Congress introduces something like ten thousand bills
> per session. Some of them are about China. Not the ones with "China" in the
> title — those are easy. The ones about port security, semiconductor subsidies,
> outbound investment screening, pharmaceutical supply chains. If you handed a
> stack of those to a poli sci student and said "which of these are really about
> China," they could do it. It'd just take them the rest of their life.
>
> So the lab builds a model that does it. And that's the whole idea I want you to
> leave this video with, so here it is plainly:

**[Slide or on-screen text: "A model learns from examples, not from rules."]**

> Nobody sits down and writes out the rules for what makes a bill China-related.
> You couldn't — you'd miss half of them and the other half would be exceptions.
> Instead you show the model a few thousand bills that a human has already sorted
> into "yes, this is about China" and "no, it isn't," and the model works out the
> pattern on its own. Then you point it at bills it's never seen.
>
> That's it. That's machine learning. The hard part was never the math — the hard
> part is that somebody has to decide what counts as "about China," and that
> somebody has to be a person who understands trade policy. Which is you.
>
> So think of what you're doing this week as content analysis. You already know
> how to read a bill and say what it's about. This is that, done to ten thousand
> of them at once — which means you get to ask questions you couldn't ask before.
> Not "what does this bill say," but "what happened to the way Congress talks
> about China between 1990 and today." Different kind of question. You need the
> scale to even ask it.

> There are three notebooks between the seven of you, so each of you is asking
> one version of that question — how often China comes up in Congress across
> thirty years, what actually happens to stock prices when a tariff gets
> announced, or whether you can tell which outlet wrote a headline purely from
> how it's framed. Same move in all three: use scale to see something you can't
> see one document at a time.
>
> And that means two or three of you are on the same notebook. I've listed who
> in the START HERE doc — talk to each other. Compare what you got. You are not
> supposed to be doing this alone in a room.

---

## Part 3 — Colab, mechanically (3:00–5:45)

[SCREEN RECORDING — this is the most important section. Go slow.]

> Okay. Practical stuff. Watch my screen.

**Beat A — the file is yours (~30s)**

[Open the shared Drive folder, click a named notebook]

> This is your notebook. It has your name on it. It lives in a Google Drive
> folder I've shared with you, and your edits save automatically as you go — you
> don't have to save anything.
>
> One thing, and this is the only rule that actually matters: **do not make your
> own copy of it.** You'll see a "Copy to Drive" button up top. Don't press it.
> If you copy it, your work goes somewhere I can't see, and I won't be able to
> help you or know how you're doing. Just work in the file that has your name on
> it.

**Beat B — running a cell (~40s)**

[Hover over a cell, show the play button, click it, show the spinner, show the
green check and the little runtime counter]

> A notebook is just a stack of boxes. Some boxes are writing, some are code.
> To run a code box, you hover over it and hit the play button — or Shift+Enter,
> which is faster once you're used to it.
>
> While it's running you get a spinning circle. When it's done you get a check
> mark and a little number telling you how long it took. If a cell is spinning
> for a long time, that's usually normal — the first one especially, it's
> downloading stuff.

[Point at a ▶️ JUST RUN header, then a ✏️ YOUR TURN header]

> Every cell is labeled. "JUST RUN" means press play and don't touch it — that's
> the plumbing. "YOUR TURN" means there's something in there for you to change,
> and the notebook tells you exactly what.
>
> Under every one of those, there's a box that says what you should see when it
> works. Use those. If your output doesn't look like the box, something's off,
> and that's genuinely useful information — it's not a grade.

**Beat C — break something on purpose (~60s) [THE KEY MOMENT]**

[Go to a YOUR TURN cell. Deliberately introduce a typo — delete a closing quote
or misspell a name. Run it. Let the full red traceback fill the screen. Sit on
it for a beat.]

> Okay, so I just broke it on purpose. Look at this.
>
> This is what an error looks like. It's a wall of red, it's long, it's got
> file paths in it you've never seen, and the first time it happens to you at
> eleven at night it feels like you did something catastrophic.
>
> You did not. Nothing is broken. You cannot break this. This is the single most
> normal thing that happens in programming — I get these constantly, everyone
> gets these constantly, and the only difference between me and you right now is
> that I've stopped finding them upsetting.

[Scroll to the bottom line of the traceback]

> Also — you only ever have to read the last line. Everything above it is the
> computer showing its work. The last line is the actual complaint.

[Press Ctrl+Z. Show the cell restore. Run it. Show it work.]

> And here's the fix. Control+Z. Same undo as a Google Doc. Every single cell
> you're asked to edit is small enough that one undo puts it back exactly how it
> was. That's on purpose — I built them that way so you can poke at things
> without being careful.

**Beat D — the reset button (~30s)**

[Runtime menu → Restart session and run all]

> And if you ever get somewhere genuinely confusing — you've changed six things,
> nothing works, you don't remember what you did — this is your reset. Runtime,
> then "Restart session and run all." That wipes everything the notebook was
> holding in memory and runs it fresh from the top.
>
> It takes a minute or two to run through. That's normal. This fixes probably
> ninety percent of "it's being weird" situations.

**Beat E — the actual point (~25s)**

[CAMERA, or back to camera in corner]

> Last thing on the mechanics. You are meant to mess with these. Each notebook
> has a "Things to try" list — change the date, swap the outlet, pick a different
> senator. Do those. That's not extra credit, that's the whole point. The
> notebook running top to bottom without you touching it teaches you nothing.

---

## Part 4 — Week 2, and how to reach me (5:45–7:15)

[CAMERA]

> So that's week one. Here's why it's set up that way.
>
> Week two you're going to be annotating congressional bills. You'll get a bill,
> or a piece of one, and you make a call: is this about China, yes or no. Then
> the next one. You'll do a bunch of them.
>
> And I want to be honest that on its face that sounds like the boring part. It
> is not the boring part. Go back to what I said at the start — the model learns
> from examples that a human sorted. Those examples are what you're making. The
> lab has a classifier called RoBERTa that reads legislation, and its ceiling is
> set entirely by the quality of the labels people like you give it. Your
> judgment calls become the thing it knows.
>
> That's the actual arc here. Week one you see what this stuff can do. Week two
> you're the reason it works on bills. I'd rather you spend two weeks on
> something real and small than two weeks on something fake and impressive.

> One more thing, and then I'll let you go.

**[Slide or on-screen text: "You will get stuck. That's expected. Message me."]**

> You are going to hit something that doesn't make sense. Not might — will. It
> happens to everyone and it is not a sign you picked the wrong notebook or that
> you're not cut out for this.
>
> The failure mode I actually worry about isn't anybody finding this too hard.
> It's somebody getting stuck on a Tuesday, feeling stupid about it, closing the
> tab, and not saying anything until Friday. Please don't be that person. There
> is no such thing as a question that's too basic here — half of you have never
> opened a notebook before and I know that.
>
> Message me any time. I'll also be around live on **[DAY]** at **[TIME]** if
> you'd rather just talk it through — drop in, no need to book anything, no need
> to have a specific question ready. "I don't get it" is a complete sentence.
>
> Alright. Go run your first cell. I'm excited to see what you find.

[END]

---

## Production checklist

- [ ] Record Part 3 **after** the full Colab verification run (README TODO #2) —
      you want the screen recording to show the final, working notebooks.
- [ ] Use a notebook nobody picked (`bill_classifier`) for the screen-recorded
      demo, so you don't spoil a beat for whoever owns that track.
- [ ] Fill in office-hours **[DAY]** / **[TIME]**. Recommend day 2 or 3 — the
      stall happens at the first unexpected output, not at the end.
- [ ] Fill in the Week 1 **[DATE]** deadline in Part 1 and in the on-screen text.
- [ ] Time a full read-aloud. If it's over 10:00, cut from Part 2 — the
      content-analysis riff compresses without losing the reframe.
- [ ] Auto-captions on. Several will watch this on a phone with sound off.
- [ ] Pair with a one-page `START_HERE` doc: notebook link, notebook-mates by
      name, deadline, "don't copy the file," Ctrl+Z, Restart-and-run-all, how to
      reach you. The video sells; the doc rescues at 11pm.

## Notes on choices

- **No notebook output is shown.** The wow moment (tariff Beat 3's "priced in"
  flatline, the media Beat 1 Fox/Xinhua split) only lands if they get there
  first.
- **Part 2 carries the classifier concept** because two of the three chosen
  notebooks — congress and tariff — contain no supervised model at all. Without
  this section, Week 2 annotation arrives with no conceptual hook for those two
  interns.
- **The deliberate error in Beat C is the highest-value 60 seconds in the
  video.** For an async beginner, the barrier is never syntax; it's the belief
  that red text means personal failure.
- **The deadline and the time estimate are in Part 1, not Part 4.** A spoken,
  personal deadline is the strongest completion driver available in a fully async
  program — stronger than the "message me" reassurance in Part 4, which only
  reaches interns who are still engaged. Front-load it.
- **Notebook-mates are named deliberately.** With no live support, a peer on the
  same notebook is a second lifeline and costs you nothing.
- **Synthetic data is not mentioned on camera.** It's disclosed in the notebooks
  themselves where it's relevant, and raising it in the intro undercuts the
  motivation before they've seen anything. Put the caveat in `START_HERE` if you
  want it in writing up front.
