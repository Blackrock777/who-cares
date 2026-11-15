# Demo video: slides, script and click-path (3:00 max)

Structure: **40 s of slides → 1 min 40 s of live demo → 40 s of slides.** Seven slides. Most of the meaning is in the voice-over, not on the slides.

---

## 1. Prompt to build the slides

Paste this into Keynote's AI, Gamma, Claude, or hand it to whoever builds the deck:

> Build a 7-slide 16:9 Keynote deck in the style of an Apple keynote and of my deck "The Life of a Reel". Rules for every slide:
> - Background pure black (#000000) or pure white (#FFFFFF). No gradients, no photos, no stock images, no icons packs, no logos except where stated.
> - One typeface: SF Pro Display (fallback: Inter). Headlines Bold, 96–120 pt, tight line spacing. Secondary text Regular, 28–32 pt, grey (#8A8A8E).
> - At most 2–3 elements per slide: one big line, optionally one number or 3 small pills. Never bullet points, never paragraphs.
> - Pills: rounded rectangles, 20 pt Semibold text, 12 pt corner radius. Colours: orange #F26B3A, white #FFFFFF with black text, blue #3B8EEA.
> - Generous empty space. Centre everything unless stated.
> - Transitions: Magic Move between consecutive slides that share an element, otherwise Dissolve 0.4 s. Builds: elements appear one by one on click.
>
> Slides:
> 1. **White background.** Left: "Who Cares" (Bold 110 pt, black). Under it in grey 28 pt: "Wevion BigHack 2026 · Clienti che non esistono". Bottom left in grey 22 pt: "Presented by [Name] & [Name]". Right half: a laptop or iPhone mock-up frame (outline only) containing a screenshot of the web app hero (I'll drop it in).
> 2. **Black.** Centre, white Bold 120 pt: "€0". Below in white Bold 48 pt: "spent before you know."
> 3. **Black.** Top centre, white Bold 80 pt, two lines: "Who sees it? / What will it cost?". Below, three pills in a row on click: "1. Imagine the audience" (orange), "2. Forecast every day" (white), "3. Decide" (blue).
> 4. **White.** Centre, black Bold 120 pt: "Let's see it." Nothing else. (I cut to the screen recording here.)
> 5. **Black.** Centre, white Bold 140 pt: "58 / 60". Below in white Bold 44 pt: "fictional companies, beaten the baseline." Small grey 22 pt line at bottom: "Built from real Meta Ad Library data and public benchmarks."
> 6. **Black.** Two lines, white Bold 80 pt, appearing one per click: "AI writes the ad." then "Our model judges it." Under the second line, a thin orange underline.
> 7. **White.** Centre, black Bold 96 pt, two lines: "The customers don't exist." / "Their clicks will." Bottom centre grey 22 pt: "github.com/poojatalele/who-cares".
>
> Speaker notes: leave empty. Export a 1920×1080 PDF and keep the .key.

Screenshots for slide 1: open `web/index.html`, the hero section (white theme, Italian or English).

---

## 2. Script (≈ 430 spoken words, 2:55)

Speak slowly; pauses are fine. Timings are cumulative.

**[Slide 1 · 0:00–0:10]**
"Hi, we're [Name] and [Name], and this is Who Cares. The brief was 'Clienti che non esistono': customers who don't exist."

**[Slide 2 · 0:10–0:20]**
"Every campaign starts with a guess. Who's going to see it, which ad to run, how much to spend. And you only find out if you guessed right after you've paid."

**[Slide 3 · 0:20–0:40]**
"So we built a tool that answers those questions first. Click: it imagines the audience behind each ad set. Click: it forecasts CTR and CPM for every ad, every day, through Black Friday. Click: and it turns that into decisions. Let me show you."

**[Slide 4 → screen recording · 0:40–2:20]**

*0:40 Audience.* "These are the four audiences of the skincare brand. We weren't told who they are, so we started from real data. Thousands of real Italian ads from the Meta Ad Library tell us who skincare ads typically reach. Then each ad set's own clicks, prices and frequency move that estimate. This one sees the same people again and again, and costs more. That's retargeting, not a demographic. And when the data barely moves the answer, the card says so."

*1:00 Crowd.* "Here are a hundred simulated people drawn from that audience. Hover over one, and you see how likely she is to click."

*1:10 Forecast.* "Every ad, every day, with its margin of error. Thin line is what happened, thick line is our forecast, and the shaded band is where eighty percent of days should land. Watch prices jump at Black Week. On the two weeks before, we cut CTR error from 33 to 26 percent, and picked the best ad in eleven of twelve ad sets."

*1:35 Decide.* "Drag the budget. Clicks, price and cost per click update live, and it warns you when you go beyond anything this ad set has ever spent. On the right, where to move money, and which creative to push for Black Week."

*1:55 Studio.* "And the last step the brief asked for. Give it a product and an offer. A language model writes six new ads, but our forecaster scores every one, against the best ad already running. Honest result: none beat the current winners yet, so it tells you to test the top one, not to switch. And it flags numbers the AI made up, which happened in one ad in five. Show one to a thousand simulated people, before spending a euro."

**[Slide 5 · 2:20–2:35]**
"One dataset proves nothing, so we generated sixty fictional companies from real sources, small and large, where we know the truth. The engine beat the baseline in fifty-eight of them, and it spotted retargeting ninety-eight percent of the time."

**[Slide 6 · 2:35–2:47]**
"Our rule: AI can write the ad. Click. But only our model gets to judge it. And it plugs into any company with one config file."

**[Slide 7 · 2:47–2:55]**
"The customers don't exist. Their clicks will. Thank you."

---

## 3. Demo click-path (record this, 1:40)

Before recording: browser full screen, zoom 90%, light theme, other tabs closed. Open **`web/index.html`** (static, no network needed). The studio shows the pre-generated runs, so no live API call can fail on camera.

| Time | Do | Say (from script) |
|---|---|---|
| 0:40 | Scroll from the hero to **Audience**. Brand: Nuvola Derma Lab. Click the **AS4** card (warm chip). | audience lines |
| 1:00 | Scroll to the crowd, hover 2–3 dots | crowd line |
| 1:10 | **Forecast**: click AS1, toggle **CPM** to show the Black Week jump, hover the Black Friday day | forecast lines |
| 1:35 | **Decide**: drag the slider to ~1.5×, point at the orange "extrapolated" warning, then the moves card | decide lines |
| 1:55 | **Studio**: audience NDL-AS1, scroll to candidate 1, point at the dotted benchmark line and the "Numbers not in the brief" chip, click **Show it to 1,000 simulated people** | studio lines |
| 2:20 | Cut back to slides | |

Optional (only if you have 10 seconds spare): click **IT** in the top bar to show the page switching to Italian.

Keynote: record the slides with Keynote's **Play → Record Slideshow** (records voice too), record the browser with **QuickTime → New Screen Recording**, join them in iMovie. Or present everything live and screen-record once.

---

## 4. Submission copy (short)

**Title:** Who Cares: Clienti che non esistono

**Description:** Who Cares reconstructs the audience behind each ad set from its own numbers, starting from real Italian Meta Ad Library reach data. It forecasts CTR and CPM for every ad and every day from 16 to 30 November with 80% ranges, and turns the forecasts into budget, creative and timing decisions. A creative studio lets a language model write new ads while our forecaster scores them. We validated the engine on 60 fictional companies built from public sources. AI used: Claude (Anthropic) for development, and Nemotron 3 Ultra via OpenRouter for ad copy.
