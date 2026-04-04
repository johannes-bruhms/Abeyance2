# Abeyance II — Cognitive Overload & Channel Capacity: Research Context

## 1. Miller's Law: What It Actually Claims

George Miller's 1956 paper "The Magical Number Seven, Plus or Minus Two: Some Limits on Our Capacity for Processing Information" is one of the most cited papers in psychology, but also one of the most frequently mischaracterized. The paper makes two distinct claims that are often conflated:

### 1.1 Absolute Judgment (Channel Capacity)

The primary argument concerns **absolute judgment** — the ability to identify stimuli along a single perceptual dimension. Miller surveyed experiments in which participants were asked to categorize tones by pitch, visual stimuli by brightness, salt solutions by concentration, etc. The consistent finding was that people could reliably distinguish roughly **5–9 categories** (mean ~7) along any single dimension before errors increased sharply. Miller framed this in information-theoretic terms: the human perceptual system has a channel capacity of approximately 2.5 bits per dimension.

Crucially, this limit applies to **unidimensional** judgments. When stimuli vary along multiple dimensions simultaneously (e.g., tones varying in both pitch and loudness), the total channel capacity increases — but sub-additively, not multiplicatively. Each additional dimension adds less than 2.5 bits.

**Timescale:** Essentially instantaneous. This is about a single perceptual act — hear a tone, assign it a label. Duration is not the operative variable; the number of available categories is.

**Source:** Miller, G. A. (1956). The magical number seven, plus or minus two: Some limits on our capacity for processing information. *Psychological Review*, 63(2), 81–97.

### 1.2 Short-Term Memory Span

The second part of Miller's paper discusses **memory span** — how many "chunks" of information a person can hold in working memory at once. This is the "7 ± 2" that became famous. The key insight is that chunking allows people to effectively increase capacity by grouping items into meaningful units (e.g., remembering "FBI-CIA-IBM" as three chunks rather than nine letters).

**Timescale:** Roughly **15–30 seconds** without active rehearsal. Items in short-term memory decay or are displaced by new input within this window.

**Source:** Miller (1956), ibid. See also: Baddeley, A. D. (2003). Working memory: Looking back and looking forward. *Nature Reviews Neuroscience*, 4(10), 829–839.

### 1.3 Cowan's Revision

Nelson Cowan argued in 2001 that Miller's "7 ± 2" conflated true attentional capacity with the effects of rehearsal and chunking strategies. When these are controlled for, the capacity of the **focus of attention** is closer to **3–5 items** (mean ~4). This has been widely replicated and is now the more commonly accepted figure in cognitive science.

**Source:** Cowan, N. (2001). The magical number 4 in short-term memory: A reconsideration of mental storage capacity. *Behavioral and Brain Sciences*, 24(1), 87–114.

---

## 2. Beyond Miller: What the Abeyance System Actually Tests

A pianist performing with the Abeyance II system is not making one-shot absolute judgments, nor is she simply holding items in memory. She is engaged in **real-time divided attention** — simultaneously monitoring her own playing, the system's autonomous responses, and the evolving relationship between the two. This places the relevant literature in several overlapping domains:

### 2.1 Multiple Object Tracking (MOT)

Pylyshyn and Storm (1988) demonstrated that people can independently track roughly **4–5 moving objects** among distractors. This limit appears to be hard — it does not improve significantly with practice and is remarkably consistent across individuals. The task is analogous to a pianist monitoring multiple simultaneous element activations in the Abeyance system: each active element produces a distinct auditory stream that the performer must track to respond coherently.

**Relevance to Abeyance:** If the system activates 3 elements simultaneously, a skilled performer may be able to attend to all three responses and adjust their playing accordingly. At 5–6 simultaneous activations, the MOT literature predicts that the performer will begin "losing" streams — failing to track which response corresponds to which gesture, defaulting to global rather than element-specific reactions.

**Source:** Pylyshyn, Z. W., & Storm, R. W. (1988). Tracking multiple independent targets: Evidence for a parallel tracking mechanism. *Spatial Vision*, 3(3), 179–197.

### 2.2 Multiple Resource Theory

Wickens' Multiple Resource Theory (MRT) proposes that attention is not a single undifferentiated pool but is divided across multiple resource dimensions: visual vs. auditory, spatial vs. verbal, perception vs. response. Tasks that draw on different resource pools can be performed more effectively in parallel than tasks that compete for the same pool.

In the Abeyance system, the performer's resources are divided between:
- **Motor output** (playing the piano — kinesthetic/motor resource)
- **Auditory monitoring** (hearing the system's responses — auditory/perceptual resource)
- **Cognitive classification** (identifying which element triggered which response — central processing)
- **Strategic planning** (deciding how to respond to the system — central/executive resource)

MRT predicts that the bottleneck will be in **central processing** — the performer can physically play and hear simultaneously (different resource pools), but *making sense of* multiple simultaneous element activations and *deciding how to respond* competes for the same executive resource. This is where overload should manifest.

**Source:** Wickens, C. D. (2002). Multiple resources and performance prediction. *Theoretical Issues in Ergonomics Science*, 3(2), 159–177.

### 2.3 Auditory Stream Segregation

Bregman's Auditory Scene Analysis framework describes how the auditory system parses a complex sound field into distinct "streams." Factors that promote stream segregation include: pitch separation, spatial separation, timbral difference, and rhythmic independence. Factors that promote fusion include: pitch proximity, temporal synchrony, and similar articulation.

**Relevance to Abeyance:** For the performer to experience N simultaneous element activations as N *distinct* information channels (rather than as undifferentiated noise), the swarm responses for each element must be **perceptually segregable**. If two elements produce responses in the same register with similar rhythmic profiles, they will fuse into a single auditory stream regardless of their distinct generative origins. The performer would then experience fewer channels than the system actually activates, undermining the cognitive overload design.

This has direct implications for swarm response design:
- Responses should occupy **different registers** where possible
- Responses should have **different rhythmic densities** (e.g., element A produces rapid notes, element B produces sustained chords)
- Responses should have **different dynamic profiles** (velocity variation)
- Temporal separation (staggered onset) promotes segregation over simultaneous onset

**Source:** Bregman, A. S. (1990). *Auditory Scene Analysis: The Perceptual Organization of Sound*. MIT Press.

### 2.4 The Attentional Blink and Temporal Resolution

The attentional blink (Raymond, Shapiro, & Arnell, 1992) demonstrates that after attending to one event, there is a ~200–500ms window during which a second event is likely to be missed. This suggests a minimum temporal grain for conscious attentional shifts.

**Relevance to Abeyance:** The 250ms analysis frame is at the lower boundary of attentional resolution. Two element activations occurring in successive 250ms frames may be perceived as simultaneous (or the second may fall in the attentional blink of the first). The performer's subjective experience of "how many things are happening" likely integrates over a window of **1–3 seconds**, not individual frames. The EMA smoothing in the classifier already operates on this timescale implicitly, which is well-aligned with the perceptual reality.

**Source:** Raymond, J. E., Shapiro, K. L., & Arnell, K. M. (1992). Temporary suppression of visual processing in an RSVP task: An attentional blink? *Journal of Experimental Psychology: Human Perception and Performance*, 18(3), 849–860.

---

## 3. Implications for the Abeyance II System Design

### 3.1 How Many Elements Can Be Tracked?

Synthesizing the MOT, MRT, and Cowan literatures, the prediction is:

| Simultaneous Elements | Expected Performer Experience |
|---|---|
| 1–2 | Comfortable. Performer can identify which elements are active and respond deliberately. |
| 3–4 | Challenging but manageable. Corresponds to Cowan's attentional focus limit. Performers may begin simplifying their playing to reduce cognitive load. |
| 5–6 | Overload. Performer cannot independently track all active channels. Responses become global (reacting to the system as a whole) rather than element-specific. This is the region of interest for studying cognitive saturation. |

The 6-element taxonomy is well-sized for this purpose — it exceeds the expected tracking limit by 1–2 elements, which means full activation should reliably produce overload without requiring an unwieldy number of gesture categories.

### 3.2 Perceptual Distinguishability Is the Prerequisite

The channel capacity question only applies if each element activation is experienced as a *distinct event*. If the swarm responses for elements A and D sound similar, the performer collapses them into one channel and the effective element count drops. Before studying overload, the system must demonstrate that performers can reliably identify at least 4–5 of the 6 elements by their swarm response alone. This could be tested with a simple forced-choice identification task prior to the performance study.

### 3.3 Observable Indicators of Saturation

For the thesis, the dependent variables that evidence cognitive overload include:

- **Gesture simplification:** As simultaneous element count increases, performers reduce the complexity of their own playing (fewer distinct gesture types, longer dwell time on single gestures).
- **Response latency:** Time between a new element activation and the performer's deliberate reaction increases.
- **Loss of hand independence:** Performers default to similar gestures in both hands rather than maintaining distinct gestural streams.
- **Channel collapse:** Performers stop responding to individual elements and begin reacting to the system's overall activity level as a single undifferentiated stimulus.
- **Self-report:** Post-performance interviews in which performers describe their subjective experience of the threshold at which they "lost the thread."

All of these can be derived from the session log data the system already captures, combined with post-performance analysis and performer interviews.

### 3.4 Framing for the Thesis

The strongest framing is not "this system proves Miller's law" but rather:

> *The Abeyance II system operationalizes the concept of cognitive channel capacity in the context of live piano performance. By controlling the number of simultaneously active gesture-response channels, the system creates conditions under which the performer's attentional limits become observable through measurable changes in gestural complexity, response latency, and strategic behavior. The system serves as both a compositional tool and a research instrument for studying the boundaries of human cognitive bandwidth in real-time musical interaction.*

This positions Miller's law as the **motivating framework** and Cowan, Pylyshyn, Wickens, and Bregman as the **operative theories** that inform the system design and the measurable predictions.

---

## 4. Swarm Response Design: Perceptual Distinguishability

For the cognitive overload study to be valid, each element's swarm response must function as a **distinct auditory stream** (Bregman, 1990). If two elements produce similar responses, the performer perceptually fuses them into one channel, reducing the effective element count below what the system reports.

### 4.1 Response Behavior Design

Each element's response is designed to differ along multiple auditory dimensions:

| Element | Response | Register | Rhythm | Duration | Relationship to Input |
|---------|----------|----------|--------|----------|----------------------|
| A (Linear Velocity) | Counter-motion | Neighboring (±1 octave) | Sequential, moderate | 0.4s | Directional inversion |
| B (Vertical Density) | Sustained resonance | Same register | Simultaneous onset | 2.5s (long) | Held chord, quiet wash |
| C (Transposed Shapes) | Tritone echo | +6 semitones | Sequential, fast | 0.3s | Shape preservation, harmonic shift |
| D (Oscillation) | Phase-shifted trill | Same pitches | Alternating, offset rate | 0.15s (staccato) | Rhythmic interference |
| E (Sweeps) | Reverse sweep | Same range | Very fast chromatic | 0.12s (percussive) | Directional opposition |
| F (Extreme Registers) | Fill the gap | Middle register | Spaced, gentle | 1.0s | Spatial complement |

These differ on the key Bregman segregation cues: **pitch register** (A, C, and F displace; B, D, E stay local), **temporal pattern** (B sustains; D and E are fast; A and C are moderate; F is slow), and **relationship to input** (each creates a unique performer-system interaction).

### 4.2 Dynamics-Neutral Detection, Dynamics-Aware Response

A critical design decision: MIDI velocity is **excluded** from the 8D gestalt vector used for classification. A trill is a trill whether it is played pp or ff — dynamics are orthogonal to gestural shape.

However, the swarm's response velocity is derived from the performer's input velocity through element-specific **dynamic mappings**. Each mapping creates a different feedback loop character:

| Mapping | Character | Perceptual Effect |
|---------|-----------|-------------------|
| Compressed (A) | Subordinate | Response follows but never dominates — the performer leads |
| Inverse (B) | Compensating | System fills the opposite dynamic — creates balance |
| Direct (C) | Mirroring | 1:1 reflection — the most transparent relationship |
| Expanded (D) | Polarizing | Quiet gets quieter, loud gets louder — heightens tension |
| Escalating (E) | Provocative | System always responds louder — pushes toward climax |
| Averaged (F) | Mediating | System finds the middle ground — stabilizing presence |

These dynamic behaviors add a second layer of cognitive demand: the performer must track not only *what* each element sounds like, but *how it responds to their dynamics*. This is directly relevant to the overload study — at low element counts, performers can learn and exploit these relationships; at high counts, managing multiple distinct dynamic feedback loops simultaneously should produce observable strategy collapse.

### 4.3 Predicted Interaction Dynamics

When multiple elements activate simultaneously, their responses interact in musically complex ways:
- **A + D** (mutually exclusive): Cannot co-occur, preventing confusion between linear motion and oscillation.
- **B + E**: Dense chord triggers quiet sustained resonance while a sweep triggers a loud reverse sweep — maximally contrasting responses that should remain segregable.
- **B + F**: Dense chords at the extremes trigger both quiet resonance (B, inverse dynamics) and gentle middle-register fill (F) — the full piano range becomes active.
- **C + D + E** (C/E mutually exclusive): At most two can co-occur, but shape echoes at tritone intervals plus phase-shifted trills create a dense contrapuntal texture that is cognitively demanding to parse.

The prediction from MOT and Cowan's literature is that performers will manage 2–3 of these interactions comfortably, begin simplifying at 4, and show clear overload behavior at 5–6 simultaneous activations.

## 5. Key Sources

- Baddeley, A. D. (2003). Working memory: Looking back and looking forward. *Nature Reviews Neuroscience*, 4(10), 829–839.
- Bregman, A. S. (1990). *Auditory Scene Analysis: The Perceptual Organization of Sound*. MIT Press.
- Cowan, N. (2001). The magical number 4 in short-term memory: A reconsideration of mental storage capacity. *Behavioral and Brain Sciences*, 24(1), 87–114.
- Miller, G. A. (1956). The magical number seven, plus or minus two: Some limits on our capacity for processing information. *Psychological Review*, 63(2), 81–97.
- Pylyshyn, Z. W., & Storm, R. W. (1988). Tracking multiple independent targets: Evidence for a parallel tracking mechanism. *Spatial Vision*, 3(3), 179–197.
- Raymond, J. E., Shapiro, K. L., & Arnell, K. M. (1992). Temporary suppression of visual processing in an RSVP task: An attentional blink? *Journal of Experimental Psychology: Human Perception and Performance*, 18(3), 849–860.
- Wickens, C. D. (2002). Multiple resources and performance prediction. *Theoretical Issues in Ergonomics Science*, 3(2), 159–177.
