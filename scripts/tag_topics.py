"""Assign one primary topic and a one-line stance to every paper.

Fully deterministic, no model calls:

* topic        - keyword scoring against data/taxonomy.yaml (title matches
                 weigh title_boost times more than abstract matches; the
                 venue's own category string adds native_boost per pattern).
                 `generic_keywords` are everywhere-a-LLM-words: they only count
                 when they appear in the title, and a topic flagged
                 `catch_all` never wins a tie, so a specific topic that matches
                 at all outranks the catch-all.
* stance_summary - the paper's own claim sentence, with the authorial framing
                 ("we argue that", "this position paper argues that", "in this
                 position paper,") stripped off, so what is left reads as a
                 claim. Candidates without a finite verb are rejected and the
                 next one is tried; if the abstract states no claim sentence at
                 all the title's claim clause is used and marked "(from title)".

Because both are heuristics they are drafts, and the README says so.
"""

from __future__ import annotations

import html
import os
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402

LATEX_SYMBOLS = {
    r"\varepsilon": "ε", r"\epsilon": "ε", r"\alpha": "α", r"\beta": "β", r"\gamma": "γ",
    r"\delta": "δ", r"\Delta": "Δ", r"\lambda": "λ", r"\Lambda": "Λ", r"\mu": "μ",
    r"\pi": "π", r"\Pi": "Π", r"\sigma": "σ", r"\Sigma": "Σ", r"\theta": "θ",
    r"\Theta": "Θ", r"\tau": "τ", r"\phi": "φ", r"\varphi": "φ", r"\rho": "ρ",
    r"\eta": "η", r"\kappa": "κ", r"\omega": "ω", r"\Omega": "Ω", r"\chi": "χ",
    r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥", r"\neq": "≠", r"\approx": "≈",
    r"\times": "×", r"\cdot": "·", r"\pm": "±", r"\infty": "∞", r"\in": "∈",
    r"\notin": "∉", r"\subset": "⊂", r"\subseteq": "⊆", r"\cup": "∪", r"\cap": "∩",
    r"\rightarrow": "→", r"\to": "→", r"\leftarrow": "←", r"\Rightarrow": "⇒",
    r"\Leftrightarrow": "⇔", r"\mathbb{R}": "ℝ", r"\mathbb{N}": "ℕ",
}

# The paper's own way of saying "here is the position". Each pattern returns the
# claim clause itself, so the framing never reaches the README. Order matters:
# the most explicit ("we argue that") first.
_STANCE_CUES = [
    # "We (argue and demonstrate) that X" - the paired-verb form is common in
    # empirical position papers, which hedge their claim with the evidence for it.
    r"\b(?:we|i|the\s+authors?|our\s+team)\s+"
    r"(?:hereby\s+|therefore\s+|jointly\s+|again\s+|ultimately\s+|finally\s+|simply\s+"
    r"|accordingly\s+|consequently\s+|explicitly\s+|strongly\s+)?"
    r"(?:argu(?:e|es|ed)|contend(?:s|ed)?|claim(?:s|ed)?|assert(?:s|ed)?|maintain(?:s|ed)?"
    r"|posit(?:s|ed)?|hold|believe(?:s|d)?|insist(?:s|ed)?|think|would\s+like\s+to\s+argue"
    r"|take\s+the\s+(?:central\s+)?position)"
    r"(?:\s+and\s+(?:\w+ly\s+)?(?:demonstrat(?:e|es|ed)?|show(?:s|ed|n)?|prove(?:s|d)?|argu\w*"
    r"|support\w+))?\s+that[,;:]?\s+(?P<c>.+)",
    r"\b(?:this|our|my|the|a)\s+(?:position\s+|invited\s+)?(?:paper|article|work|note|essay"
    r"|monograph|position)\s+(?:here\s+)?(?:argu(?:es|e|ed)|contend(?:s|ed)?|claim(?:s|ed)?"
    r"|assert(?:s|ed)?|maintain(?:s|ed)?|posit(?:s|ed)?|advocate(?:s|d)?|urges?|recommends?"
    r"|demands?|develops?|takes\s+the\s+position|makes?\s+the\s+case"
    r"|presents?\s+the\s+view)\s+(?:the\s+view\s+)?that[,;:]?\s+(?P<c>.+)",
    r"\b(?:our|my|this|(?:the|this)\s+(?:central|main|core|overall|general|authors'))\s+"
    r"(?:position|thesis|claim|argument|stance|viewpoint|opinion|belief|conviction)\s+"
    r"(?:is|remains|stands|argues)\s+(?:that[,;:]?\s+)?(?P<c>.+)",
    # "This position paper is a call to arms for the certification community, ..."
    # - the claim is the call itself, so the noun phrase is kept as it stands.
    r"\b(?:this|our|my)\s+(?:position\s+|invited\s+)?(?:paper|article|work|essay)"
    r"\s+is\s+(?P<c>a\s+(?:call|plea|appeal|manifesto|case)\b.+)",
    r"\b(?P<c>(?:we|i|they|the\s+authors?)\s+(?:hereby\s+|therefore\s+|jointly\s+|strongly\s+"
    r"|urgently\s+|ultimately\s+|overall\s+)?(?:call\s+for|call\s+on|argue\s+for|plead\s+for|make\s+the"
    r"\s+case\s+for|urge|advocate|recommend|demand|push\s+for)\s+.+)",
    r"\bit\s+is\s+(?:our|my|the)\s+(?:position|view|belief|conviction|argument)\s+that[,;:]?\s+(?P<c>.+)",
    # "This paper proposes a Right to AI, which asserts that individuals should
    # participate" - the proposal is named first and the claim lives in the
    # relative clause, so a literal strip of the framing would leave a fragment.
    r"\b(?:this|our|my|the)\s+(?:position\s+|invited\s+)?(?:paper|work|article|essay)"
    r"\s+(?:proposes?|introduces?|presents?|advances?|articulates?|develops?|outlines?"
    r"|puts\s+forward)\s+[^.]{0,140}?\b(?:which|that)\s+(?:asserts?|argues?|contends?"
    r"|holds?|maintains?|claims?|means?)\s+that[,;:]?\s+(?P<c>.+)",
    # "The goal of this position paper is to argue that X" / "Our aim is to show that X".
    r"\b(?:the|our|my)\s+(?:[a-z]+\s+)?(?:goal|aim|purpose|objective|argument|thesis|claim"
    r"|position|view)(?:\s+of\s+this\s+(?:position\s+|invited\s+)?(?:paper|work|article|essay))?"
    r"\s+is\s+(?:to\s+)?(?:argu(?:e)?|contend|advocate|show|demonstrate|make\s+the\s+case"
    r"|convince\s+readers\s+that|persuade)\s+(?:the\s+reader\s+)?(?:that[,;:]?\s+)?(?P<c>.+)",
    # "This paper calls for X" - the call is the stance, no "that" clause involved.
    r"\b(?:this|our|my|the)\s+(?:position\s+|invited\s+)?(?:paper|work|article|essay)"
    r"\s+(?:hereby\s+|jointly\s+|also\s+)?calls?\s+for\s+(?P<c>.+)",
]

# Framing that can sit in front of an already-extracted claim. Each pattern
# requires a stance verb, so a leading "we must ..." or "the paper industry ..."
# is left alone.
LEAD_FRAMING = [
    r"^(?:in|within|throughout)\s+this\s+(?:position\s+)?(?:paper|article|work|note|essay)s?\s*[:,]?\s+",
    r"^(?:this|our|my|the)\s+(?:position\s+)?(?:paper|article|work|note|essay)s?\s+(?:here\s+)?"
    r"(?:argu(?:e|es|ed)|contend(?:s|ed)?|claim(?:s|ed)?|assert(?:s|ed)?|maintain(?:s|ed)?"
    r"|advocate(?:s|d)?|urges?|recommends?|demands?|develops?|makes?\s+the\s+case"
    r"|presents?\s+the\s+view)\s*(?:the\s+view\s+)?(?:that|for)?\s*[:,]?\s+",
    r"^(?:we|i|they|the\s+authors?)\s+(?:hereby\s+|therefore\s+|jointly\s+|strongly\s+|again\s+"
    r"|ultimately\s+|finally\s+|simply\s+|accordingly\s+|consequently\s+|explicitly\s+)?"
    r"(?:argu(?:e|es|ed)|contend(?:s|ed)?|claim(?:s|ed)?|assert(?:s|ed)?|maintain(?:s|ed)?"
    r"|posit(?:s|ed)?|believe(?:s|d)?|insist(?:s|ed)|think|hold|take\s+the\s+position"
    r"|would\s+like\s+to\s+argue)\s*(?:\s*,\s*[^,.]{1,40}\s*,)?\s*(?:that|:)?\s+",
    r"^(?:our|my|the|this)\s+(?:central\s+|main\s+|core\s+|overall\s+)?(?:position|thesis|claim"
    r"|argument|stance|view|viewpoint)\s+(?:is|remains|stands|argues)\s*(?:that\s*)?[:,]?\s+",
    r"^(?:as\s+authors?|as\s+a\s+community)\s*[:,]\s*",
]

# Compiled: the framing is usually the first words of a sentence, so the
# patterns have to match a capitalised "We argue that" / "This paper contends".
STANCE_CUES = [re.compile(p, re.IGNORECASE) for p in _STANCE_CUES]

# A sentence that states what ought to be, without saying "we argue". "X carries
# risks of Y" is not a stance, so a bare noun like "risk" is not a cue here.
NORMATIVE = re.compile(
    r"\b(?:should|must|ought\s+to|needs?\s+to|requires?\s+(?:to|us|that|that\s+we)"
    r"|is\s+(?:essential|critical|imperative|necessary|required|vital|urgent)"
    r"|are\s+(?:essential|critical|imperative|necessary|required|vital|urgent)"
    r"|cannot|can\s*not|fail(?:s|ed|ure)?\s+to|it\s+is\s+time\s+to"
    r"|(?:demands?|requires?|needs?|warrants?)\s+(?:a|an|the|better|more)"
    # "Achieving this requires rethinking evaluation" - X requires Y-ing.
    r"|(?:demands?|requires?|needs?|warrants?)\s+(?:\w+ly\s+)?[a-z]+ing\b)", re.I)

NOISE_START = re.compile(
    r"^(?:we\s+(?:note|observe|show|argue|contend)\s+that[,:\s]+)"
    r"|^(?:however|moreover|furthermore|additionally|therefore|thus|hence)[,:\s]+", re.I)

# Where a position paper stops summarising the field and starts arguing with it.
CONTRAST = re.compile(
    r"^(?:however|yet|but|nevertheless|nonetheless|still|in\s+contrast|by\s+contrast"
    r"|despite|while|although|though|unfortunately|critically|contrary)\b", re.I)

# A judgement about how things are reads as a stance even without a "should":
# "certified robustness remains insufficient for practice", "the potential of AI
# researchers is largely untapped". Closed list of the evaluative words position
# papers reach for, so a neutral descriptive sentence is not swept in.
EVAL_ADJ = (r"(?:insufficient|inadequate|untapped|unverifiable|problematic|risky|unsafe"
            r"|unsustainable|misguided|flawed|wrong|harmful|perishable|unreliable"
            r"|ineffective|counterproductive|questionable|unjust|inequitable|missing|lacking"
            r"|necessary|essential|urgent|obsolete|illusory|impossible|untenable|fragile"
            r"|not\s+(?:enough|sufficient|appropriate|reliable))")
EVALUATIVE = re.compile(
    r"\b(?:is|are|remains?|was|were|becomes?|become|proves?)\s+(?:not\s+)?"
    r"(?:largely\s+|still\s+|fundamentally\s+|simply\s+|often\s+|inherently\s+|increasingly\s+)?"
    + EVAL_ADJ + r"\b"
    # The same judgement as a causative, with the object in between: "has
    # rendered the centralized conference model increasingly unsustainable".
    r"|\b(?:render(?:s|ing|ed)?|make|makes|made)\s+(?:\S+\s+){0,5}?" + EVAL_ADJ + r"\b", re.I)

# A claim needs a finite verb. FUNCTION_PREDICATE is a closed class (modals,
# copula, auxiliaries); MAIN_VERBS is a short, deliberately incomplete list of
# the verbs position statements turn on. One of them must appear early in the
# candidate: a "verb" that only shows up after a long appositive or relative
# clause ("SPINE, a unified framework that treats ...") means the candidate is
# a noun phrase, not a claim, and it is rejected in favour of the next one.
FUNCTION_PREDICATE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|am|do|does|did|have|has|had|will|would|shall|should"
    r"|can|cannot|ca ?n't|could|may|might|must|ought|need|dare)\b", re.I)
MAIN_VERB_STEMS = [
    "argue", "contend", "claim", "assert", "maintain", "posit", "call", "advocate",
    "recommend", "urge", "demand", "require", "need", "deserve", "warrant", "prefer",
    "fail", "lack", "exceed", "risk", "matter", "work", "help", "hurt", "cost", "pay",
    "allow", "enable", "prevent", "reduce", "increase", "improve", "weaken", "undermine",
    "strengthen", "build", "design", "define", "mean", "indicate", "show", "demonstrate",
    "provide", "offer", "give", "take", "make", "use", "adopt", "adapt", "shift", "move",
    "grow", "change", "replace", "outperform", "perform", "persist", "hold", "stand",
    "break", "stop", "start", "begin", "continue", "lead", "result", "translate",
    "constitute", "represent", "reflect", "regulate", "govern", "enforce", "ban", "win",
    "lose", "become", "remain", "stay", "come", "transform", "evaluate", "measure",
    "test", "support", "oppose", "accept", "reject", "prioritize", "rethink",
    "reconsider", "differ", "emerge", "exist", "shape", "fit", "suit", "apply", "depend",
    "benefit", "suffer", "struggle", "threaten", "endanger", "limit", "constrain",
    "outweigh", "scale", "miss", "drive", "bring", "run", "face", "avoid", "leave",
    "overlook", "compromise", "challenge", "reshape", "withstand", "understate",
    "overstate", "obscure", "blur", "erode", "ignore",
    "made", "gave", "took", "held", "became", "came", "led", "lost", "won", "met", "ran",
]
MAIN_VERBS = re.compile(
    r"\b(?:" + "|".join(MAIN_VERB_STEMS) + r")(?:s|es|ed|d|ing)?\b", re.I)
PREDICATE_WINDOW = 16

SUBORDINATE_START = re.compile(
    r"^(?:since|while|although|though|because|when|whenever|if|unless|after|before|despite"
    r"|nor|and|but|or|so|yet|both|either|neither|for|to|via|versus|upon)\b", re.I)

ABBR = re.compile(r"\b(?:e\.g|i\.e|vs|etc|cf|Dr|Prof|Fig|Sec|No|St|i|II|III)\.(?=\s|$)")


def clean_text(text: str) -> str:
    """Flatten LaTeX markup and whitespace into README-safe plain text."""
    if not text:
        return ""
    s = str(text)
    s = re.sub(r"\\(?:cite[tp]?\*?|nocite)\{[^{}]*\}", " ", s)
    s = re.sub(r"\\(?:ref|eqref|pageref|label)\{[^{}]*\}", " ", s)
    s = re.sub(r"\\(?:TeX|LaTeX)\b", "LaTeX", s)
    for cmd in sorted(LATEX_SYMBOLS, key=len, reverse=True):
        s = re.sub(re.escape(cmd) + r"(?![a-zA-Z])", LATEX_SYMBOLS[cmd], s)
    for _ in range(3):
        s = re.sub(r"\\(?:text|textbf|textit|texttt|emph|underline|mathrm|mathbf"
                   r"|mathbb|mathcal|operatorname|mbox)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"[_^]\{[^{}]*\}", "", s)
    # A hyphen at a line break in the original abstract ("noncom- pliance"): the
    # space is an artefact, not a hyphenated compound.
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s)
    s = re.sub(r"\\(?:left|right|big|Big|bigg|Bigg)\b", "", s)
    s = re.sub(r"\\[a-zA-Z]+\s?", "", s)
    s = (s.replace("``", '"').replace("''", '"').replace("$", "")
            .replace("{", "").replace("}", "").replace("\\", ""))
    # A few venue exports ship the abstract with Markdown emphasis still in it.
    s = s.replace("**", "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def sentences(text: str) -> list[str]:
    """Split into sentences without breaking on "e.g." / "i.e." / initials."""
    guarded = ABBR.sub(lambda m: m.group(0)[:-1] + "\u2063", text or "")
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'($])", guarded)
    return [p.replace("\u2063", ".").strip() for p in parts if p.strip()]


# Words that can only precede a noun: "for standardized evaluation" is a
# participial adjective, "has rendered the model obsolete" is the verb.
NP_PRE = frozenset("""a an the this that these those there its their theirs his her
ours my your our he she it they them we you i all any both each every few more most
much many neither no none other others several some such both either neither and or but
nor so than as at by for from in into of on onto over per through to under upon with
within without versus via so yet both done given""".split())


def _finite_morph(clause: str, window: int) -> bool:
    """A conservatively read inflected verb: lies / matters / rendered / remains.

    MAIN_VERBS can only ever be a sample of English, so a claim whose verb is not
    on that list ("a key lies in addressing ...") would otherwise be thrown away.
    A token ending in -s/-es/-ies/-ed counts only when it is not sitting right
    after a determiner or preposition (then it is a noun or an adjective) and not
    at the very end of the clause (nothing left for a verb to govern).
    """
    words = [re.sub(r"[^A-Za-z'-]", "", w) for w in clause.split()]
    for i, w in enumerate(words[:window]):
        low = w.lower()
        if i == 0 or i == len(words) - 1:
            continue
        if not re.fullmatch(r"[a-z]{4,}(?:ies|es|s|ed)", low):
            continue
        if low.endswith(("ss", "us", "is", "as", "ous", "ive", "ness", "ms", "xs")):
            continue
        if words[i - 1].lower().rstrip(".,;:") in NP_PRE:
            continue
        return True
    return False


def has_predicate(clause: str, full: bool = False) -> bool:
    """True when the clause reads as a claim rather than a noun phrase.

    Asides push the main verb out of reach, so parentheticals, quotes and
    dash-set-off appositives are dropped first - this only decides whether a
    candidate is printed, never what is printed. `full` widens the search from
    the first PREDICATE_WINDOW words to the whole clause, which the stance-cue
    tier can afford: there the framing ("we argue that ...") already proved the
    sentence is a claim, so only a headless noun phrase should be rejected.
    """
    core = re.sub(r"\([^()]*\)", " ", clause or "")
    core = re.sub(r"[\"“”].*?[\"“”]", " ", core)
    for dash in (" -- ", " — ", " – "):
        parts = core.split(dash)
        if len(parts) >= 3:
            core = parts[0] + " " + " ".join(parts[2:])
            break
    words = [w for w in re.findall(r"[^\s]+", core) if re.search(r"\w", w)]
    limit = len(words) if full else PREDICATE_WINDOW
    window = " ".join(words[:limit])
    return bool(FUNCTION_PREDICATE.search(window) or MAIN_VERBS.search(window)
                or _finite_morph(core, limit))


def score_topic(spec: dict, title_l: str, blob_l: str, native_l: str, tax: dict) -> tuple[int, int]:
    """(score, generic_part) for one topic against one paper."""
    boost = int(tax.get("title_boost", 3))
    native_boost = int(tax.get("native_boost", 4))
    generic_title = int(tax.get("generic_title_boost", 2))
    score = generic = 0
    for kw in spec.get("keywords") or []:
        if re.search(r"\b" + re.escape(kw.lower()), title_l):
            score += boost
        elif re.search(r"\b" + re.escape(kw.lower()), blob_l):
            score += 1
    # "LLM", "language model", "foundation model": true of most of the corpus,
    # so an abstract mention carries no information and is not scored at all.
    # The title mention is reported separately, because it says nothing about
    # what kind of paper this is.
    for kw in spec.get("generic_keywords") or []:
        if re.search(r"\b" + re.escape(kw.lower()), title_l):
            score += generic_title
            generic += generic_title
    for nat in spec.get("native") or []:
        if re.search(r"\b" + re.escape(nat.lower()), native_l):
            score += native_boost
    return score, generic


def classify(text_blob: str, native_topic: str, taxonomy: dict,
             title: str) -> tuple[str, str, int]:
    """Return (topic_key, label, score) for one paper.

    Generic LLM vocabulary has the lowest priority, twice over: a
    `generic_keywords` hit only counts when it is in the title, and it is
    subtracted from the `catch_all` topic before that topic is allowed to win.
    So "Language models & reasoning" takes a paper only on the strength of
    words that actually describe its subject (reasoning, prompting, tokens),
    never merely because the title says "LLM". Ties go to the earlier topic in
    data/taxonomy.yaml.
    """
    title_l, blob_l, native_l = title.lower(), text_blob.lower(), (native_topic or "").lower()
    scored = []
    for key, spec in taxonomy["topics"].items():
        score, generic = score_topic(spec, title_l, blob_l, native_l, taxonomy)
        scored.append((key, spec["label"], score, bool(spec.get("catch_all")), generic))
    specific = [t for t in scored if not t[3]]
    generic_only = [t for t in scored if t[3]]
    best_spec = max(specific, key=lambda t: t[2]) if specific else None
    best_catch = max(generic_only, key=lambda t: t[2]) if generic_only else None
    sp = best_spec[2] if best_spec else 0
    ca = best_catch[2] - best_catch[4] if best_catch else 0
    if best_catch and ca > sp:
        return best_catch[:3]
    if best_spec and sp > 0:
        return best_spec[:3]
    fallback = next((t for t in scored if t[0] == taxonomy.get("default_topic", "other")),
                    best_spec or best_catch)
    return fallback[:3]


def stance(title: str, abstract: str) -> str:
    """One clean claim sentence: what the paper argues, without the framing.

    Four tiers, best evidence first: the paper's own stance sentence ("we argue
    that X", "our position is that X"), a normative sentence ("X should Y"), a
    sentence that judges how things are ("X remains insufficient for Y"), and
    finally the title with an explicit "(from title)" marker. Every candidate
    must read as a clause with a finite verb, so noun-phrase scraps are skipped
    rather than printed.

    The two framing-free tiers only look from the first contrast onwards
    ("However, ..."): what comes before it is the background the paper is about
    to reject, and printing it would attribute the field's opinion to the paper.
    """
    text = clean_text(abstract or "")

    def usable(claim: str, full: bool = False) -> bool:
        return bool(claim) and not ROADMAP.match(claim) and is_claim(claim, full=full)

    for sent in sentences(text):
        for cue in STANCE_CUES:
            m = re.search(cue, sent)
            if m:
                claim = polish(strip_framing(m.group("c")))
                # The cue already says this is the position, so accept a verb
                # anywhere in the clause, not only in its first sixteen words.
                if usable(claim, full=True):
                    return _clip(claim)
    sents = sentences(text)
    raw = [polish(strip_framing(NOISE_START.sub("", s))) for s in sents]
    # Index of the first sentence that starts a turn against the background.
    turn = next((i for i in range(1, len(sents)) if CONTRAST.match(sents[i])), 0)
    for lo, hi in ((turn, len(raw)), (0, turn)):
        for claim in raw[lo:hi]:
            if NORMATIVE.search(claim) and usable(claim):
                return _clip(claim)
        for claim in raw[lo:hi]:
            if EVALUATIVE.search(claim) and usable(claim):
                return _clip(claim)
    clause = title_clause(title) or title_clause(clean_text(title))
    return _clip(f"{clause} (from title)") if clause else ""


FRAMING_TAIL = re.compile(r"[\s,;:]+$|[\s]+(?:is argued|should be adopted)\.$", re.I)

# A sentence about what the paper does ("we formalize ...", "this paper
# introduces ...") is a roadmap, not a stance: the candidate is rejected and the
# next one tried, which is what AGENTS asks for when no claim sentence exists.
ROADMAP = re.compile(
    r"^(?:we|i|they|the\s+authors?|authors"
    r"|this\s+(?:position\s+|invited\s+)?(?:paper|work|article|essay|study|note)"
    r"|our\s+(?:paper|work|article|study|contribution))\s+"
    r"(?:\w+ly\s+|hereby\s+|jointly\s+|also\s+|first\s+|next\s+|then\s+|finally\s+)*"
    r"(?:formaliz[ez]\w*|introduc\w*|describ\w*|outline\w*|discuss\w*|examin\w*|review\w*"
    r"|conclud\w*|substantiat\w*|illustrat\w*|explor\w*|investigat\w*|summariz\w*|report\w*"
    r"|develop\w*|construct\w*|offer\w*|provide\w*|highlight\w*|categoriz\w*|classif\w*"
    r"|compar\w*|walks?\s+through|surve(?:y|ys|ied)|present[s]?\b|propose[sd]?\b"
    r"|propos\w*|put\s+forward|is\s+devoted|aims?\b|seeks?\b|takes\s+the\s+position)\b", re.I)

# Where a claim stops being a claim and the paper starts describing itself.
PAPER_RESUMES = re.compile(
    r"\s+and\s+(?:thus\s+|further\s+)?(?:the\s+)?(?:paper|article|work|study|we|i)\b"
    r"|\s+and\s+(?:proposes?|discusses?|outlines?|presents?|describes?|introduces?"
    r"|demonstrates?|highlights?|emphasiz\w+|argues?|advocates?|illustrates?|examines?"
    r"|sheds?\s+light|sheds?|provides?|gives?|shows?|supports?|explores?|surveys?|reviews?)\b"
    r"|\s+(?:specifically|in\s+particular|concretely)\s*,")


# "We call on the community to publish the data" cannot be stripped down to a
# clause with a verb, so the addressee is promoted to the subject of an ought.
CALL_ON = re.compile(
    r"^(?:we|i|they|the\s+authors?|authors)\s+(?:\w+ly\s+|hereby\s+|jointly\s+)*"
    r"(?:call\s+on|urge[sd]?|encourage[sd]?|ask[s]?|exhort[s]?)\s+"
    r"(?P<np>[a-z].{2,70}?)\s+to\s+(?P<vp>.+)$", re.I)

# The same for a call with no addressee: "We advocate systematic methodologies
# for X" has no reading once the "we" is gone, so the object becomes the subject
# of a need - "Systematic methodologies for X are needed."
CALL_FOR = re.compile(
    r"^(?:we|i|they|the\s+authors?|authors)\s+(?:\w+ly\s+|hereby\s+|jointly\s+|also\s+)*"
    r"(?:call\s+for|advocate\s+for|advocate|argue\s+for|plead\s+for|push\s+for"
    r"|campaign\s+for|make\s+the\s+case\s+for|recommend[sd]?|support|back|demand[sd]?)\s+"
    r"(?!that\b|to\b)(?P<np>.{4,}?)(?:\s+to\s+(?P<vp>.+))?$", re.I)

HEAD_STOP = re.compile(
    r"(?:of|for|in|to|with|on|at|by|from|as|into|over|under|among|against|during|per"
    r"|that|which|who|whose|where|when|and|or|nor|but|than|-)", re.I)


def _np_head(noun_phrase: str) -> str:
    """The head noun of a noun phrase: the first token the next one depends on."""
    tokens = [t.strip(",.;:()\"'“”") for t in noun_phrase.split()]
    for i, tok in enumerate(tokens):
        if not tok or tok.lower() in ("a", "an", "the"):
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if not nxt or HEAD_STOP.fullmatch(nxt) or nxt.endswith(","):
            return tok
    return tokens[-1] if tokens else ""


def _numbered(head: str) -> bool:
    w = head.lower()
    return w.endswith(("s", "ies")) and not w.endswith(("ss", "us", "is", "as", "ns", "mas"))


def _call(clause: str) -> str:
    m = CALL_ON.match(clause)
    if m:
        who, what = m.group("np").strip(), m.group("vp").strip()
        return f"{who[:1].upper()}{who[1:]} should {what}"
    m = CALL_FOR.match(clause)
    if m and m.group("vp"):
        who = m.group("np").strip()
        who = who[:1].lower() + who[1:]
        return _call(f"we call on {who} to {m.group('vp').strip()}")
    if m:
        noun_phrase = m.group("np").strip().rstrip(".;:")
        verb = "are needed" if _numbered(_np_head(noun_phrase)) else "is needed"
        return f"{noun_phrase[:1].upper()}{noun_phrase[1:]} {verb}."
    return ""


def strip_framing(clause: str) -> str:
    """Peel author framing off the front of a clause until only the claim is left."""
    clause = (clause or "").strip().strip("\"'“”‘’").strip()
    for pat in (CALL_ON, CALL_FOR):
        if pat.match(clause):
            out = _call(clause)
            if out:
                return out
            break
    seen = None
    while seen != clause:
        seen = clause
        clause = clause.strip().lstrip(",:;- ")
        clause = re.sub(r"^(?:that|this|the)\s+(?:main\s+|central\s+)?(?:claim|argument|position"
                        r"|thesis|point)\s+(?:is|that)\s+(?:that\s+)?", "", clause, flags=re.I)
        # "We question this trend, arguing that algorithms should ..." - the
        # claim is the participle's object, the first words are the act of arguing.
        clause = re.sub(r"^(?:we|i|they|this\s+(?:position\s+)?(?:paper|work|article)"
                        r"|the\s+paper|our\s+paper)[^,.]{0,60}?,\s+(?:argu(?:ing|es|ed)"
                        r"|maintaining|holding|contending|asserting|positing|suggesting)"
                        r"\s+(?:the\s+view\s+)?that[,;:]?\s+", "", clause, flags=re.I)
        for pat in LEAD_FRAMING:
            new = re.sub(pat, "", clause, count=1, flags=re.I)
            if new.strip() != clause.strip():
                clause = new
                break
        clause = re.sub(r"^(?:that|:|,)\s+", "", clause.strip()).strip()
    return FRAMING_TAIL.sub("", clause.strip())


def is_claim(text: str, full: bool = False) -> bool:
    """A stance is a clause: long enough, finite verb early, not a dependent tail."""
    if not text:
        return False
    words = text.split()
    if len(words) < 5 or not (20 <= len(text) <= 420):
        return False
    if SUBORDINATE_START.match(text):
        return False
    if re.match(r"^(?:however|moreover|furthermore|additionally|therefore|thus|hence|in\s+addition"
                r"|for\s+example|specifically|overall|finally|second|third)\b", text, re.I):
        return False
    return has_predicate(text, full=full)


def polish(text: str) -> str:
    """Make the extracted clause read as a standalone sentence."""
    s = re.sub(r"\s+", " ", text or "").strip()
    # Abstracts copied out of HTML/LaTeX keep a space before punctuation.
    s = re.sub(r"\s+([,.;:!?)\]])", r"\1", s)
    # "we argue that X, and that Y" - the second "that" belonged to the framing.
    s = re.sub(r"\s*,\s*and\s+that\s+", "; ", s, flags=re.I)
    # "(i) addressing X is essential ..." - a stance never opens on a list marker.
    s = re.sub(r"^\(?(?:[ivxIVX]{1,4}|\d{1,2})[)\].]\s+(?=.)", "", s)
    s = re.sub(r"\[\s*", "(", s)
    s = re.sub(r"\s*\]", ")", s)
    # The claim ends where the paper's own roadmap resumes ("... and we discuss",
    # "... and proposes a framework"), which would otherwise read as nonsense.
    s = re.split(PAPER_RESUMES, s, maxsplit=1)[0].strip()
    s = s.strip("\"'“”‘’").strip()
    s = re.sub(r"^[(\[]\s*", "", s)
    s = FRAMING_TAIL.sub("", s)
    # "Emerging accountability challenges in COLS: users are billed for
    # operations they cannot observe" - when the label in front of the colon is
    # not itself a claim (or is only the paper announcing itself), the claim is
    # the part the colon introduces.
    m = re.match(r"^(?P<lead>[^.:;!?]{3,90})\s*:\s+(?P<c>[A-Z].+)$", s)
    if m and has_predicate(m.group("c"), full=True) and (
            not has_predicate(m.group("lead")) or ROADMAP.match(m.group("lead"))):
        s = m.group("c")
    if s.count("(") > s.count(")"):
        s = re.sub(r"\s*\([^()]*$", "", s)
    # A clause cut off inside an "(i) ... (ii) ..." enumeration ends on a bare
    # lower-case letter or roman numeral; "AI." or "FAI." must survive (no /i).
    s = re.sub(r"(?:\s+|\()\s*(?:i|ii|iii|iv|v|e|g|i\.e|e\.g|for)\.?$", "", s)
    s = FRAMING_TAIL.sub("", s).strip()
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if s and s[-1] not in ".!?":
        s += "."
    return s


def title_clause(title: str) -> str:
    """The title with the "Position:" marker removed; its own words, untouched."""
    clause = re.sub(r"^\s*Position(?:\s+Paper)?\s*[:!?.-]+\s*", "", clean_text(title)).strip()
    return re.sub(r"\s+", " ", clause).rstrip(".!?").strip()


def _clip(s: str, limit: int = 300) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(",;:and or but")
    return cut.rstrip(".!?") + "…"


def tag_rows(rows: list[dict], taxonomy: dict | None = None) -> list[dict]:
    taxonomy = taxonomy or load_taxonomy()
    for r in rows:
        title = clean_text(r.get("title", ""))
        abstract = r.get("abstract", "") or ""
        blob = f"{title}. {abstract}"
        key, label, score = classify(blob, r.get("native_topic", "") or "", taxonomy, title)
        r["topic"] = label
        r["_topic_key"] = key
        r["_topic_score"] = score
        r["stance_summary"] = stance(title, abstract)
        r["title"] = title
        r["abstract"] = clean_text(abstract)
    return rows


def load_taxonomy() -> dict:
    return C.load_taxonomy(os.path.join(C.DATA, "taxonomy.yaml"))


def main() -> None:
    """Re-tag data/papers.csv in place (used by run_all after collection)."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    ap.add_argument("--report", action="store_true", help="print topic distribution")
    args = ap.parse_args()

    rows = C.read_csv(args.csv)
    tax = load_taxonomy()
    tag_rows(rows, tax)
    C.write_csv(rows, args.csv)

    from collections import Counter
    dist = Counter(r["topic"] for r in rows)
    weak = [r for r in rows if int(r.get("_topic_score", 0)) == 0]
    print(f"tagged {len(rows)} rows into {len(dist)} topics; "
          f"{len(weak)} with no keyword hit (default topic)")
    if args.report:
        for label, n in dist.most_common():
            print(f"  {n:4d}  {label}")


if __name__ == "__main__":
    main()
