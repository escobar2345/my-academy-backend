# -*- coding: utf-8 -*-
"""
topic_library.py - Real curriculum content for auto-generated student textbooks.
Keyed by the EXACT topic names in CAREER_ROADMAPS monthly plans. Each topic has
detailed lessons, key terms, common mistakes, practice work and topic-unique
quiz questions. Quiz sets are disjoint across topics, so the three month books
never repeat each other's questions.
"""

TOPICS = {}

# ======================================================================
# MONTH 1 - Design Foundations & Tools
# ======================================================================

TOPICS["Design Principles"] = {
    "summary": "The visual grammar every composition is judged by: balance, contrast, hierarchy, alignment, proximity, repetition, white space and movement.",
    "lessons": [
        ("What design principles are and why they matter",
         "Design principles are the rules our eyes already obey. When a poster feels 'off', the cause is almost always weak contrast, unaligned elements or scattered related items. Learning the principles turns vague 'I don't like it' into a specific, fixable diagnosis. Professionals choose which principles will CARRY a given design - a luxury flyer leans on white space and alignment; a concert poster leans on contrast and movement - then enforce them consistently."),
        ("Balance: symmetrical, asymmetrical and radial",
         "Symmetrical balance mirrors elements around a centre line: formal, calm, institutional. Asymmetrical balance places unequal elements whose visual weights still cancel out - a large photo left, headline plus two short paragraphs right - and feels modern and dynamic. Radial balance arranges everything around a centre point, ideal for badges and event posters. Quick test: squint at the layout; if one side 'sinks', lighten, move or resize elements until the page feels stable."),
        ("Contrast and visual hierarchy",
         "Hierarchy is the reading order you impose: headline first, sub-head second, body third, footer last. Build it with size (2x steps, not 1.1x), weight, colour and position. Contrast is the strongest tool - if two levels differ by less than about 30-40% in size, viewers cannot tell which matters. Never size body text above the sub-head, and never use two similar blues for supposedly different levels."),
        ("Alignment, proximity and repetition",
         "Alignment means every element shares an invisible line with another; arbitrary placement is the number one beginner giveaway, so snap everything to a grid. Proximity groups related items - captions under their photos, contact details in one block. Repeating the same button style, spacing and corner radius across the layout is what makes work feel designed rather than assembled."),
        ("White space and movement",
         "White space is not wasted space; it is the frame that lets content breathe and the most important element own the emptiest area. Cramped layouts read as cheap - increase margins and line spacing before shrinking content. Movement steers the eye: a diagonal image, an arrow, a repeated accent colour appearing beside the call-to-action. Trace where your own eye lands first, second, third - that path IS your design."),
    ],
    "terms": [
        ("Visual weight", "How strongly an element pulls the eye - driven by size, colour, darkness and position."),
        ("Grid", "An invisible network of columns and rows that elements snap to for alignment."),
        ("Negative space", "The empty areas around and between elements; they shape meaning as much as content does."),
        ("Focal point", "The single element a composition is built to emphasise."),
        ("Contrast", "The difference in size, colour or weight that makes elements distinguishable."),
    ],
    "mistakes": [
        "Using three sizes that are nearly the same instead of two clearly different sizes.",
        "Centring everything, which kills hierarchy and makes pages look like school handouts.",
        "Filling every empty area - no breathing room, no focal point.",
    ],
    "practice": [
        "Take any event flyer and mark where the eye lands 1st, 2nd, 3rd - name the principle that created that order.",
        "Rebuild the same information twice: once symmetrical, once asymmetrical. Compare the feeling each version gives.",
        "Design a quote card using ONE typeface, two colours and generous white space.",
    ],
    "quiz": [
        {"q": "Placing a caption directly beneath its photo uses which principle?", "options": ["Proximity", "Radial balance", "Repetition", "Contrast"], "answer": 0},
        {"q": "A large photo on the left balanced by a text block on the right is:", "options": ["Symmetrical balance", "Asymmetrical balance", "Radial balance", "No balance"], "answer": 1},
        {"q": "The main purpose of white space is to:", "options": ["Save printing cost", "Let content breathe and create focus", "Fill empty areas", "Increase text size"], "answer": 1},
        {"q": "Which change creates the clearest heading/body hierarchy?", "options": ["16px to 17px", "Same size, different font", "Double the heading size and add weight", "Colour both navy"], "answer": 2},
        {"q": "Repeating the same button style across a page demonstrates:", "options": ["Proximity", "Repetition/consistency", "Contrast", "Movement"], "answer": 1},
    ],
}

TOPICS["Colour Theory"] = {
    "summary": "The colour wheel, harmonies, psychology, accessibility contrast and building a working brand palette in RGB, HEX and CMYK.",
    "lessons": [
        ("The wheel and the three properties of colour",
         "Colour has three properties: hue (the colour family - red, teal), saturation (intensity - neon vs dusty) and value/lightness (light vs dark). Every palette decision is really a decision about these three sliders. The 12-part wheel arranges primary, secondary and tertiary colours. Screens mix light (RGB, additive); print mixes ink (CMYK, subtractive) - which is why vivid screen designs print darker."),
        ("Harmonies that always work",
         "Monochrome (one hue, varied values) is the safest, most elegant scheme. Analogous neighbours (teal-blue-green) feel calm and cohesive. Complementary opposites (blue-orange) give maximum punch for calls-to-action. For any scheme use the 60/30/10 rule: 60% dominant colour, 30% secondary, 10% accent - and the accent is reserved for the ONE action you want seen or clicked."),
        ("Colour psychology in branding",
         "Colour carries learned associations: blue = trust and finance, green = health and growth, red = urgency and appetite, yellow = optimism and budget, black = luxury, purple = creativity. These are tendencies, not laws - context and culture matter. Pick the primary from the brand's promise, then differentiate with the accent. Test: describe the brand in three words and check each colour supports at least one."),
        ("Contrast, accessibility and readability",
         "Text must pass contrast ratios: at least 4.5:1 for normal text, 3:1 for large text (WCAG). Forty-percent grey on white fails; near-black on white passes. Never rely on colour alone to communicate - pair it with an icon or label. Body text reads best in near-black or dark navy; pure black on pure white vibrates on screens, and coloured paragraphs strain the eye."),
        ("Building a brand palette",
         "A working palette contains: one primary, one or two secondaries, one accent, neutrals (off-black, greys, off-white) and success/warning/error colours. Document every colour in HEX (screens), RGB (digital) and CMYK/Pantone (print) so vendors match exactly. Build from a base hue in HSL: rotate hue for secondaries, drop saturation for neutrals, raise lightness for tints - then save everything as swatches so you never eyeball colours twice."),
    ],
    "terms": [
        ("Hue", "The colour family itself, measured in degrees on the colour wheel."),
        ("Saturation", "A colour's intensity; desaturated colours look grey or muted."),
        ("Tint / shade", "A hue mixed with white (tint) or black (shade)."),
        ("Complementary", "Colours opposite each other on the wheel; maximum contrast when paired."),
        ("WCAG contrast ratio", "The measured brightness difference between text and background; 4.5:1 minimum for body text."),
    ],
    "mistakes": [
        ("Using colour alone to carry meaning", "Red/green status text is invisible to colour-blind users; pair colour with an icon, label or shape."),
        ("Rainbow palettes", "More than three hues in one design reads as amateur; pick a dominant, a support and one accent."),
        ("Ignoring print conversion", "A neon RGB palette prints dull - check the CMYK build of every brand colour before sending files."),
        ("Low-contrast body text", "Light grey paragraphs look elegant on the designer's monitor and unreadable on a phone in daylight."),
    ],
    "practice": [
        "Build a 60/30/10 palette in HSL for a coffee brand; export HEX, RGB and CMYK values to a swatch sheet.",
        "Recolour one flyer in monochrome, analogous and complementary schemes; note what each communicates.",
        "Run three brand colours through a contrast checker and note which pair fails for body text.",
    ],
    "quiz": [
        {"q": "Which three properties fully describe a colour?", "options": ["Red, green, blue", "Hue, saturation, value", "Tint, tone, shade", "Cyan, magenta, yellow"], "answer": 1},
        {"q": "The safest, most elegant palette for a brand is usually:", "options": ["Complementary", "Monochrome", "Triadic primary", "Random pastel"], "answer": 1},
        {"q": "The 60/30/10 rule reserves 10% of a layout for:", "options": ["Body text", "The accent on the main action", "White space", "Headings"], "answer": 1},
        {"q": "Minimum WCAG contrast ratio for normal body text is:", "options": ["1.5:1", "3:1", "4.5:1", "10:1"], "answer": 2},
        {"q": "Why can a vivid RGB palette disappoint when printed?", "options": ["Printers are slow", "CMYK ink cannot reproduce every RGB colour", "RGB files are larger", "Pantone is mandatory"], "answer": 1},
    ],
}

TOPICS["Typography"] = {
    "summary": "Type families, scales, spacing, hierarchy and the rules that make text easy to read and worth reading.",
    "lessons": [
        ("Anatomy and the big families",
         "Every letterform has parts: baseline, x-height, ascender, descender, stem, bowl. X-height drives perceived size - a large x-height reads bigger at the same point size. Serifs feel editorial and traditional, sans-serifs clean and modern, display faces carry personality but set headlines only, while scripts and slab faces are accents, never body text."),
        ("Scales, sizing and rhythm",
         "Build a type scale instead of choosing sizes by eye: 12 / 16 / 24 / 36 / 54 / 80px (roughly 1.5x steps) so every size relates to the others. Body text sits at 15-18px on screens, 45-75 characters per line, with line-height about 1.4-1.6x the font size. Headlines can tighten to 1.1-1.2x because capitals leave optical gaps."),
        ("Hierarchy through weight and spacing",
         "Hierarchy is not only size: weight, colour, letter-spacing and space all signal importance. Use two weights of one family (Semibold + Regular) rather than two families. Space above a heading should be about double the space below it, so the heading visibly belongs to the text it introduces instead of the block above."),
        ("Kerning, tracking and alignment",
         "Tracking opens up all-caps labels; kerning fixes awkward pairs such as 'AV' and 'To'. Tighten display headlines slightly and never body text. Left-align anything longer than three lines; centre only short headings and single-line calls to action. Justified text without hyphenation creates rivers of white space - avoid it on screen."),
        ("Pairing fonts and avoiding cliches",
         "Safe pairings contrast in one dimension only: serif headline with sans body, or condensed headline with humanist body. Confirm a font carries the characters you need - currency symbols, accents, tabular numerals for tables. Two families maximum per project; consistency beats variety."),
    ],
    "terms": [
        ("X-height", "Height of lowercase letters excluding ascenders and descenders; drives perceived size."),
        ("Tracking", "Uniform space added between every letter in a word or heading."),
        ("Kerning", "Optical adjustment of space between two specific letters."),
        ("Leading", "Vertical distance between lines, usually a multiple of the font size."),
    ],
    "mistakes": [
        ("Two similar sans-serif families", "Readers cannot tell why the font changed, so the design looks accidental."),
        ("Long centred paragraphs", "Centred text forces the eye to hunt for each line's start."),
        ("All-caps body text", "Capitals remove word-shape cues and noticeably slow reading."),
        ("Faux bold and script faces for paragraphs", "Synthetic styles and scripts destroy legibility at length."),
    ],
    "practice": [
        "Set one paragraph in three type scales and mark which reads fastest.",
        "Pair a serif and a sans-serif for a one-page flyer; justify the pairing in two sentences.",
        "Set a line of all-caps and adjust tracking until it stops looking cramped.",
    ],
    "quiz": [
        {"q": "A font's perceived size at a given point size is driven mainly by its:", "options": ["Ascenders", "X-height", "Serifs", "Kerning"], "answer": 1},
        {"q": "Comfortable line-height for body text is about:", "options": ["0.9x", "1.0x", "1.4-1.6x", "3x"], "answer": 2},
        {"q": "Space above a heading should generally be:", "options": ["Equal to the space below", "Half the space below", "About double the space below", "Irrelevant"], "answer": 2},
        {"q": "Tracking is most usefully applied to:", "options": ["Body paragraphs", "All-caps labels", "Every heading", "Tables of numbers"], "answer": 1},
        {"q": "Which content should be left-aligned?", "options": ["Long paragraphs", "A one-line button", "A wedding invitation line", "A logo lockup"], "answer": 0},
    ],
}
TOPICS["Layout"] = {
    "summary": "Grids, composition, visual hierarchy across a page, and the mechanics that make a layout feel intentional.",
    "lessons": [
        ("Why grids exist",
         "A grid is a set of columns, gutters and margins decided BEFORE designing, so every element has a home and the page stays consistent across pages. Use 12 columns for flexible splits, 4-6 for simple posters. Margins should be generous: 8-10% of the page width reads professional, 2% reads cramped."),
        ("Composition and focal point",
         "Every layout needs one dominant element; if two compete, the viewer decides for you. Work the hierarchy in reading order: headline, image, support text, action. Use rule-of-thirds placement for the focal point rather than dead-centring everything, and let one element break the grid deliberately to add energy."),
        ("Proximity, alignment and the space between",
         "Group related things tightly and separate unrelated things clearly - space communicates relationship more honestly than lines or boxes. Align every element to a grid line; a single stray edge makes a whole layout look unfinished. Measure the space between blocks and reuse those exact values so rhythm stays consistent."),
        ("Templates and multi-page consistency",
         "Once a page works, turn it into a template: master margins, column grid, type scale, colour roles and reusable components. A magazine, deck or report looks designed only because the SAME decisions repeat on every page. Keep a consistent header and footer zone and vary only the content area."),
        ("Critique: fixing a weak layout",
         "Diagnose before redecorating. Ask where the eye lands first, what is unclear, and what the least necessary element is. Common fixes are removing one element, increasing the space around the focal point, strengthening the heading scale, and aligning to one grid line. Remove before adding."),
    ],
    "terms": [
        ("Grid", "Columns, gutters and margins that elements snap to for alignment."),
        ("Gutter", "The space between columns or between grid modules."),
        ("Focal point", "The single element the composition is built to emphasise."),
        ("Rule of thirds", "Dividing the canvas into thirds so key elements land on the lines or intersections."),
    ],
    "mistakes": [
        ("Too many focal points", "Competing heroes mean no hero at all."),
        ("Ignoring margins", "Content glued to the page edge looks cheap and unprofessional."),
        ("Uneven spacing", "Random gaps between blocks destroy rhythm."),
        ("No grid on multi-page work", "Each page drifts until the set stops looking like one document."),
    ],
    "practice": [
        "Rebuild one weak poster on a 12-column grid and note every alignment you had to correct.",
        "Design a 2-page spread using one template with a fixed header, footer and type scale.",
        "Take a layout you like and measure its margins, gutters and spacings as percentages of the page.",
    ],
    "quiz": [
        {"q": "How many columns does a flexible print or screen grid typically use?", "options": ["2", "5", "12", "24"], "answer": 2},
        {"q": "Professional-looking page margins are around:", "options": ["0-1% of width", "8-10% of width", "25% of width", "Whatever remains"], "answer": 1},
        {"q": "Why should only one element dominate a layout?", "options": ["Because printers limit ink", "So the viewer's first glance is directed", "It saves time", "Grids require it"], "answer": 1},
        {"q": "Space between blocks communicates:", "options": ["Print cost", "Whether items are related", "File size", "Colour accuracy"], "answer": 1},
        {"q": "The first step when fixing a weak layout is:", "options": ["Add decoration", "Diagnose where the eye lands and remove what is unnecessary", "Change fonts", "Shrink margins"], "answer": 1},
    ],
}
TOPICS["Logo Design"] = {
    "summary": "From brief to final lockup: research, sketching, construction, refinement, variants and delivery of a logo that works everywhere.",
    "lessons": [
        ("Brief and research",
         "A logo is a compressed argument about a brand. Extract what the business does, who it serves, what it must never look like, where the logo will live (signage, app icon, invoice) and which competitors to avoid resembling. Collect 20-30 references and write WHY each works. Skipping this stage is why beginners produce pretty marks that answer no question."),
        ("Sketching, then digitising",
         "Produce 30-50 fast pencil thumbnails covering wordmarks, monograms, pictorial marks, abstract marks, emblems and combination marks. Quantity first, judgement later - the best idea usually appears past thumbnail 20. Circle three directions, digitise those in vector, then build only the strongest properly."),
        ("Geometry and optical correction",
         "Construct with circles, squares and consistent stroke weights so the mark feels inevitable rather than drawn. Then break the maths where the eye disagrees: overshoot rounded shapes slightly past the baseline, thin crossing points, and keep horizontal strokes slightly thinner than verticals. Optical balance beats mathematical exactness."),
        ("Testing at every size and colour",
         "A logo must survive at 16px favicon scale and on a building. Shrink it, blur it, print it in one colour and reverse it onto dark stock. Reduce complexity until it reads at thumbnail size, and check the favicon before you fall in love with the detail."),
        ("Delivering the lockup system",
         "Deliver a primary lockup, a stacked variant, an icon-only mark, one-colour and reversed versions, plus clear-space and minimum-size rules measured from an element of the mark (usually cap height). Specify SVG, transparent PNG and EPS or PDF exports with the colour values for each version."),
    ],
    "terms": [
        ("Wordmark", "A logo built purely from the brand name set in custom type."),
        ("Monogram", "A mark built from the brand's initials."),
        ("Pictorial mark", "A recognisable image used as the logo."),
        ("Clear space", "The protected margin around a logo where nothing else may sit."),
    ],
    "mistakes": [
        ("Starting in software", "Clicking around in Illustrator before sketching locks you into the first workable idea."),
        ("Trend-chasing gradients", "Trends date fast and make the mark look like everyone else's."),
        ("No size test", "Detailed marks turn to mush at invoice or favicon scale."),
        ("Only one version", "Clients need horizontal, stacked, icon, mono and reversed variants from day one."),
    ],
    "practice": [
        "Sketch 30 logo directions in 15 minutes for a fictional bakery; digitise the best two.",
        "Rebuild a favourite logo on a circle grid and note where you broke the grid optically.",
        "Deliver one logo as a 5-file system with written clear-space and minimum-size rules.",
    ],
    "quiz": [
        {"q": "A logo exploration should start with how many thumbnails?", "options": ["1-3", "5-10", "30 or more", "Exactly 100"], "answer": 2},
        {"q": "Optical correction means:", "options": ["Copying maths exactly", "Adjusting shapes so they LOOK balanced", "Using only circles", "Centring everything"], "answer": 1},
        {"q": "Which format is essential for web logos?", "options": ["JPEG", "SVG", "PSD", "DOCX"], "answer": 1},
        {"q": "Clear space is measured from:", "options": ["The page edge", "An element of the logo such as its cap height", "The client's choice", "The stroke of text below"], "answer": 1},
        {"q": "A monogram logo uses:", "options": ["A full photograph", "The brand initials", "A mascot", "Slogan text"], "answer": 1},
    ],
}
TOPICS["Brand Identity"] = {
    "summary": "Turning a logo into a repeatable visual language: palette, type, graphic device, templates and the guidelines that hold it together.",
    "lessons": [
        ("From logo to identity",
         "A logo is one asset; an identity is a system. Identity decides how the brand looks across cards, posts, invoices and signage so customers recognise it before reading the name. Every element - colour, type, shape, photography - must reinforce the same three brand adjectives, or the system contradicts itself."),
        ("Building the flexible element set",
         "Design a small kit: logo lockups, a palette with usage ratios, two typefaces with a scale, a graphic device (shape, pattern or frame), an image treatment and layout templates. The device is what carries recognition where the logo cannot fit, so it must be simple enough to redraw from memory."),
        ("Tone of voice",
         "Language is part of identity. Define how the brand speaks - formal or playful, technical or warm - and write example headlines and captions so copy and design stay aligned. A visual identity with a mismatched tone still feels like two different companies."),
        ("Documenting and rolling out",
         "Write guidelines a stranger could follow: colour values in HEX, RGB and CMYK, the type scale with fallbacks, spacing rules, do-and-don't examples and file-naming conventions. Then apply the system to ten real touchpoints (post, poster, invoice, card, signature, deck) and fix whatever breaks. Consistency is the entire point."),
    ],
    "terms": [
        ("Brand guidelines", "The rulebook that keeps every brand asset consistent."),
        ("Graphic device", "A shape, pattern or frame carrying brand recognition without the logo."),
        ("Touchpoint", "Any place a customer meets the brand, print or digital."),
        ("Tone of voice", "The personality and register of a brand's written language."),
    ],
    "mistakes": [
        ("Logo-only branding", "With no device, palette or template, every new post is invented from scratch."),
        ("Guidelines nobody can execute", "Unmeasured, poetic rules cannot be followed by another designer."),
        ("Too many elements", "Six devices and four fonts means no recognisable system at all."),
        ("Forgetting digital sizes", "A print-first system with no social or app crops slows every campaign."),
    ],
    "practice": [
        "Extend your logo into a 10-touchpoint identity system.",
        "Write a one-page guidelines sheet: palette values, type scale, clear space and three don'ts.",
        "Design a repeatable social template using only the graphic device and type.",
    ],
    "quiz": [
        {"q": "The clearest difference between a logo and an identity is:", "options": ["Price", "Identity is a reusable system; a logo is one asset", "Identity is digital only", "There is none"], "answer": 1},
        {"q": "A graphic device matters because it:", "options": ["Replaces the logo", "Carries recognition where the logo cannot fit", "Adds page numbers", "Printers require it"], "answer": 1},
        {"q": "Good guidelines are judged by whether:", "options": ["They look beautiful", "A new designer can produce on-brand work unaided", "They exceed 100 pages", "They use latin phrases"], "answer": 1},
        {"q": "Do-and-don't examples exist to:", "options": ["Fill pages", "Show exactly where the system breaks", "Copyright the brand", "Satisfy printers"], "answer": 1},
        {"q": "Tone of voice describes:", "options": ["Font weights", "How the brand writes and speaks", "Speaker volume", "Colour temperature"], "answer": 1},
    ],
}
TOPICS["Print Production"] = {
    "summary": "Preparing files that print correctly: bleed, CMYK, resolution, paper choice, proofs and press checks.",
    "lessons": [
        ("Bleed, trim and safe areas",
         "Printers trim the sheet after printing, so artwork must extend 3mm past the trim line (bleed) while important content stays 3-5mm inside it (safe area). Files without bleed get an ugly white sliver at the edge; content in the unsafe zone gets guillotined off."),
        ("Colour for print",
         "Print uses CMYK ink, which cannot reproduce every neon RGB colour - expect darker, duller results, so convert then correct. Use rich black (C40 M30 Y30 K100) for large areas and pure black for small text, and reserve spot or Pantone colours for brand marks where exactness matters."),
        ("Resolution and file formats",
         "Print needs 300dpi at final size; doubling an image's displayed size quarters its effective resolution. Keep photos as high-quality TIFF or press-safe JPEG, never screenshots. Vector artwork stays sharp at any size, so logos and type must never be rasterised."),
        ("Stock, finishes, proofs and press checks",
         "Heavy uncoated stock and finishes such as foil, spot UV or emboss feel premium; thin gloss reads cheap, and every finish adds cost and production time. Always approve a digital proof, then a physical proof for anything the client will hold, and at the press check compare the live sheet to the proof under proper light rather than chasing a byte-perfect match."),
    ],
    "terms": [
        ("Bleed", "Extra artwork beyond the trim edge so no white sliver appears after cutting."),
        ("Trim line", "Where the printed sheet is cut to its final size."),
        ("Rich black", "A black built from all four inks for deeper, denser coverage."),
        ("Press check", "Approving the printed sheet on press before the full run."),
    ],
    "mistakes": [
        ("No bleed", "White slivers appear along trimmed edges."),
        ("RGB artwork sent to press", "Colours print dull and unpredictable."),
        ("Low-resolution images", "Photos look soft or pixelated at final size."),
        ("Skipping proofs", "Errors are found only after the whole run is printed and paid for."),
    ],
    "practice": [
        "Set up an A5 flyer with 3mm bleed, safe area and CMYK blacks; export a print-ready PDF.",
        "Compare one photo at 72dpi and 300dpi at 100% zoom.",
        "Specify a paper stock and one finish for a premium invitation and justify the cost.",
    ],
    "quiz": [
        {"q": "Standard bleed for most commercial print is:", "options": ["1mm", "3mm", "10mm", "None"], "answer": 1},
        {"q": "Print images are prepared at:", "options": ["72dpi", "150dpi", "300dpi at final size", "1200dpi"], "answer": 2},
        {"q": "Rich black is built from:", "options": ["K only", "All four process inks", "Pantone 186", "RGB values"], "answer": 1},
        {"q": "Sending RGB artwork to a CMYK press usually produces:", "options": ["Brighter output", "Duller, less predictable colour", "No change", "Automatic Pantone conversion"], "answer": 1},
        {"q": "A press check exists to:", "options": ["Increase the run length", "Approve the live sheet before full production", "Test eyesight", "Replace proofs entirely"], "answer": 1},
    ],
}
TOPICS["Photoshop"] = {
    "summary": "Raster editing done properly: layers, masks and adjustment layers, plus export settings for print and screen.",
    "lessons": [
        ("The workspace and non-destructive workflow",
         "Photoshop edits pixels, so the file IS the work. Keep the first layer as an untouched original, duplicate before experimenting, and group layers by element (background, subject, type). Use smart objects for anything you may scale, because resizing a normal layer destroys pixels permanently."),
        ("Layers, masks and adjustments",
         "A layer mask hides instead of deleting: paint black to conceal, white to reveal, grey for partial. Adjustment layers (Curves, Levels, Hue/Saturation, Colour Balance) change tone and colour above the image and stay editable forever, so a client's 'make it warmer' becomes a five-second fix instead of a rebuild."),
        ("Selections, cutouts and retouching",
         "Match the selection tool to the edge: Object Selection for clear subjects, the Pen tool for product outlines, Select and Mask for hair. Feathered 0.5-1px edges look natural, and every cutout must be checked on white AND dark backgrounds. Retouch with the Heal and Clone tools on separate layers so the original survives."),
        ("Exporting for the right destination",
         "Screen work exports as sRGB JPEG or PNG at exact pixel dimensions (1080x1080 for a post, 1920x1080 for a slide). Print work needs 300dpi at final size in CMYK with 3mm bleed, saved as PDF or TIFF. Keep a layered master PSD - exports are disposable, the master is the asset."),
    ],
    "terms": [
        ("Layer mask", "Non-destructive hiding of part of a layer using black and white paint."),
        ("Smart object", "A layer wrapper that scales and filters without destroying pixels."),
        ("Adjustment layer", "An editable tonal or colour change applied above the artwork."),
        ("dpi", "Dots per inch - resolution; 300dpi is the print standard, 72dpi is screen."),
    ],
    "mistakes": [
        ("Erasing on the original layer", "Destructive edits cannot be undone tomorrow - use masks."),
        ("Upscaling small images", "A 500px photo blown up to A4 looks soft at print size."),
        ("Designing print work in RGB", "On press the colours shift; start print files in CMYK."),
        ("Flattening the master", "Losing layers means every future change costs twice as long."),
    ],
    "practice": [
        "Composite two photos with a mask so the join is invisible.",
        "Retouch a portrait using only adjustment layers.",
        "Export one layout for print (CMYK 300dpi) and for social (sRGB 1080px) and compare.",
    ],
    "quiz": [
        {"q": "Hide part of a layer without deleting pixels by using:", "options": ["The eraser", "A layer mask", "Flatten image", "Opacity at zero"], "answer": 1},
        {"q": "Print resolution should be:", "options": ["72dpi", "150dpi", "300dpi at final size", "Whatever the camera gave"], "answer": 2},
        {"q": "A smart object protects:", "options": ["Layer order", "Quality when scaling", "Colour mode", "Fonts"], "answer": 1},
        {"q": "Which export suits Instagram?", "options": ["CMYK TIFF", "sRGB JPEG or PNG at exact pixel size", "300dpi PDF with bleed", "PSD"], "answer": 1},
        {"q": "The master PSD should be:", "options": ["Flattened at the end", "Kept with layers intact", "Deleted after export", "Converted to BMP"], "answer": 1},
    ],
}


TOPICS["Canva"] = {
    "summary": "Fast, template-driven delivery: reuse, resize and brand-lock layouts without rebuilding from scratch.",
    "lessons": [
        ("When Canva is the right tool",
         "Canva wins on speed for social posts, presentations, simple flyers and internal documents. It is the wrong tool for logos, print-ready CMYK files and anything needing exact typographic control - using a web template for those produces blurry logos and unprintable colour."),
        ("Brand kits, colours and fonts",
         "Set the brand kit up first: upload the logo files, lock the palette with exact HEX values, and choose the two brand fonts. Every template then inherits the brand automatically, which is what keeps thirty posts looking like one company rather than thirty designers."),
        ("Templates, resizing and consistency",
         "Build one master layout, then use Resize to produce story, post and banner versions, re-anchoring the content rather than stretching it. Lock elements you do not want moved, keep 20px+ margins, and save repeated blocks as your own templates."),
        ("Delivery, exports and checks",
         "Export PNG for social, PDF Print for documents and MP4 for animation. Before delivery check: is the logo crisp at full size, does text pass contrast, is every resized version readable, and has every placeholder been replaced? Fast tools still ship slow errors."),
    ],
    "terms": [
        ("Brand kit", "Stored logo, colours and fonts applied automatically to designs."),
        ("Template", "A reusable layout with locked and editable regions."),
        ("Resize", "Creating other aspect-ratio versions of one design."),
        ("Placeholder", "Stand-in text or image that must be replaced before delivery."),
    ],
    "mistakes": [
        ("Using Canva for logos", "Templates produce generic marks that cannot survive as vector files."),
        ("Editing brand colours by eye", "Hex codes must be exact or every asset drifts."),
        ("Stretching to resize", "A square post stretched into a story distorts the imagery."),
        ("Shipping placeholders", "Lorem text left in a client deck destroys credibility."),
    ],
    "practice": [
        "Build a brand kit with locked colours and two fonts, then produce three posts from one master layout.",
        "Rebuild a flyer in Canva and compare the exported PNG with the vector original.",
        "Audit five existing Canva designs against the brand kit and list every deviation.",
    ],
    "quiz": [
        {"q": "Canva is the WRONG choice for:", "options": ["Instagram posts", "Client presentations", "Vector logos for print", "Internal flyers"], "answer": 2},
        {"q": "A brand kit mainly prevents:", "options": ["Slow internet", "Colour and font drift across assets", "Large file sizes", "Template limits"], "answer": 1},
        {"q": "The right way to make a story from a square post is:", "options": ["Stretch it", "Resize and re-anchor the content", "Screenshot it", "Swap the fonts"], "answer": 1},
        {"q": "PDF Print export is used for:", "options": ["Animations", "Documents and print pieces", "Video", "Fonts"], "answer": 1},
        {"q": "Before delivery you must always:", "options": ["Add more effects", "Replace every placeholder and check the logo", "Delete the original", "Compress to 1MB"], "answer": 1},
    ],
}


TOPICS["Illustrator"] = {
    "summary": "Vector construction: paths and anchors, shape building, type as outlines and clean delivery files.",
    "lessons": [
        ("Vectors, paths and the pen tool",
         "Vector artwork is geometry - anchors, handles and curves - so a logo drawn here scales from favicon to billboard with no loss. Master the pen: place anchors only where the direction changes, keep their number low, and drag handles to shape curves. Fewer anchors means smoother, more editable work than any autotrace."),
        ("Building with shapes and Pathfinder",
         "Complex marks are simple shapes combined. Draw construction circles and rectangles on a template layer, then Unite, Minus Front, Intersect and Exclude on the artwork layer to cut the final form. Expand the result and delete stray points so the file stays light and editable."),
        ("Type as outlines and artboards",
         "Logo wordmarks must be converted with Type > Create Outlines so they display without the font installed, then customised - shave, notch or merge characters to make the mark ownable. Use one artboard per variant or size, name them properly, and export SVG for web plus PDF/EPS for print."),
    ],
    "terms": [
        ("Anchor point", "A node that defines the shape of a path."),
        ("Handle", "The direction line that bends a curve segment."),
        ("Pathfinder", "Tools that combine or subtract overlapping shapes."),
        ("Artboard", "A defined, exportable canvas area inside one file."),
    ],
    "mistakes": [
        ("Shipping autotraced sketches", "Wobbly, anchor-heavy paths read as amateur at large sizes."),
        ("Nesting raster images in logos", "A PNG inside a vector file destroys the scaling advantage."),
        ("Forgetting to outline fonts", "The client opens the file and the wordmark collapses to a default font."),
        ("One artboard for everything", "Exports become guesswork instead of a named, repeatable set."),
    ],
    "practice": [
        "Trace a sketch with the pen tool in fewer than 20 anchors.",
        "Build an icon from four basic shapes using Pathfinder only.",
        "Prepare a named export set: SVG, PDF and transparent PNG for one mark.",
    ],
    "quiz": [
        {"q": "Vector art scales without loss because it is:", "options": ["High resolution", "Mathematical geometry", "Compressed well", "Saved as PDF"], "answer": 1},
        {"q": "The pen tool works best with:", "options": ["Many anchors", "Few anchors at direction changes", "Autotrace always", "Straight lines only"], "answer": 1},
        {"q": "Create Outlines is used to:", "options": ["Add a stroke", "Convert text to shapes for safe delivery", "Rotate text", "Print faster"], "answer": 1},
        {"q": "Minus Front in the Pathfinder:", "options": ["Unites shapes", "Subtracts the top shape from the one below", "Duplicates shapes", "Blends colours"], "answer": 1},
    ],
}

TOPICS["Monograms"] = {
    "summary": "Initial-based marks: construction, locking letterforms together and keeping a monogram readable at tiny sizes.",
    "lessons": [
        ("Why initials work as a mark",
         "A monogram compresses a name into a symbol, which is why it suits small applications - app icons, buttons, embossed stationery, social avatars. It only works when the initials are read instantly: interlock or share strokes rather than simply placing letters side by side."),
        ("Construction and shared strokes",
         "Build letters on a geometric skeleton: consistent stroke weights, aligned tops and bottoms, and one deliberate point of contact or overlap. Adjust the weight of verticals against horizontals for optical balance, and rotate a wide letter slightly rather than distorting its proportions."),
        ("Readability at small sizes and lockups",
         "Test the monogram at 24px and in one colour on a dark background. If the letters merge into a blob, remove an element rather than adding detail. Deliver it as a standalone mark plus a lockup with the full name, with the same clear-space rule as any other logo."),
    ],
    "terms": [
        ("Monogram", "A logo built from a person's or brand's initials."),
        ("Lockup", "The fixed arrangement of a symbol with the brand name."),
        ("Shared stroke", "A line the two letters use in common, joining them into one form."),
        ("Optical balance", "Adjusting shapes so they look even, instead of measuring them."),
    ],
    "mistakes": [
        ("Side-by-side initials with no interaction", "It reads as text, not as a mark."),
        ("Too much detail", "Thin flourishes disappear at icon sizes."),
        ("Ignoring one-colour use", "A mark that needs two colours fails on stamps and embossing."),
        ("No full-name lockup", "New audiences cannot tell what the letters stand for."),
    ],
    "practice": [
        "Draw 12 monograms for one set of initials using shared strokes.",
        "Take the best one and test it at 32px, in one colour, on dark and light.",
        "Build a lockup with the full brand name plus clear-space rules.",
    ],
    "quiz": [
        {"q": "A monogram is built from:", "options": ["A mascot", "The initials of the name", "A full illustration", "A slogan"], "answer": 1},
        {"q": "Monograms suit small applications because they:", "options": ["Are colourful", "Compress the name into a compact symbol", "Need no testing", "Are always symmetrical"], "answer": 1},
        {"q": "When a monogram blurs at small sizes you should:", "options": ["Add detail", "Remove an element and simplify", "Change the colour", "Rotate it"], "answer": 1},
        {"q": "A lockup is:", "options": ["A storage folder", "The fixed arrangement of symbol and name", "A colour palette", "A print finish"], "answer": 1},
    ],
}


TOPICS["Poster"] = {
    "summary": "Single-sheet communication: one message, read from three metres, with hierarchy and print-ready setup.",
    "lessons": [
        ("One message, read at distance",
         "A poster is seen before it is read. Decide the single sentence a passer-by must absorb in three seconds - event, offer or warning - and make that sentence the largest element on the sheet. Everything else (details, venue, dates, QR code) sits below it in a clear second and third level."),
        ("Hierarchy, grids and layout for a sheet",
         "Work on a 6 or 12 column grid with generous margins, place the headline on the optical centre or a rule-of-thirds line, and leave one dominant image or shape rather than five competing ones. Body copy should never drop below 9pt on A3: if it will not fit, cut the words, not the size."),
        ("Type scale and legibility in the wild",
         "Set the headline at roughly 8-12x the body size, use two weights of one family, and keep all-caps for short lines only. Test legibility by shrinking the layout to A5 on screen and squinting - if the message survives, it will survive a wet lamp-post."),
        ("Print-ready artwork and finishing",
         "Build A2/A3 at 300dpi CMYK with 3mm bleed and a 5mm safe area, convert blacks properly (rich black for large areas, K-only for small text) and choose stock that suits the venue - uncoated for handwriting, gloss for images. Deliver a PDF with embedded fonts and printer marks included."),
    ],
    "terms": [
        ("Optical centre", "The point slightly above true centre where the eye expects the focus."),
        ("Safe area", "The inner zone where text survives trimming and frames."),
        ("Rich black", "A four-ink black used for large solid areas."),
        ("Imposition", "How pages are arranged on the press sheet for cutting."),
    ],
    "mistakes": [
        ("Five messages on one sheet", "Nothing is remembered when everything shouts."),
        ("Body text under 9pt on A3", "Unreadable at poster viewing distance."),
        ("No bleed", "White slivers along the trimmed edge."),
        ("Centring everything", "Flat hierarchy that reads like a school notice."),
    ],
    "practice": [
        "Redesign a cluttered event flyer to carry one message legibly at three metres.",
        "Set up an A2 poster at 300dpi CMYK with bleed, safe area and marks; export a print PDF.",
        "Print a proof at A5 and mark anything unreadable from arm's length.",
    ],
    "quiz": [
        {"q": "A poster's primary job is to:", "options": ["List every detail", "Deliver one message read at distance", "Show the designer's range", "Be readable at 20cm"], "answer": 1},
        {"q": "Minimum comfortable body size on an A3 poster is about:", "options": ["6pt", "9pt", "14pt", "24pt"], "answer": 1},
        {"q": "Poster artwork needs:", "options": ["No bleed", "300dpi CMYK with 3mm bleed and safe area", "72dpi RGB", "A 1mm margin"], "answer": 1},
        {"q": "Optical centre sits:", "options": ["Exactly in the middle", "Slightly above true centre", "At the bottom", "In the corner"], "answer": 1},
    ],
}


TOPICS["Mockups"] = {
    "summary": "Presenting design work: realistic mockups, staged visuals and a narrative that sells the idea.",
    "lessons": [
        ("Why presentation changes the decision",
         "Clients approve work they can imagine in use. The same logo that looks thin on a flat white slide looks considered on a business card, signage and an app icon. Mockups are not decoration - they are the argument that the design works in the real world."),
        ("Building convincing mockups",
         "Match the mockup to the real application: choose a scene with believable lighting and perspective, place the artwork on a smart-object layer, then match shadow direction, grain and colour temperature. Warped, over-saturated or pixel-soft placements instantly read as fake."),
        ("Sequence, narrative and delivery",
         "Present in the order a customer meets the brand: context, primary lockup, applications, then details - one idea per slide with a caption stating why. Export a PDF deck at a consistent page size with fonts embedded and every version clearly labelled, and never present a print piece as a flat JPEG."),
    ],
    "terms": [
        ("Mockup", "A staged image showing artwork on a real-world object or scene."),
        ("Smart object", "The PSD layer where artwork is placed and warped to fit."),
        ("Scene", "The photographic setting and lighting of the mockup."),
        ("Deck", "The ordered presentation of the work, usually a PDF."),
    ],
    "mistakes": [
        ("Flat-on-white presentation only", "Clients cannot judge scale, colour or material."),
        ("Badly matched perspective", "The artwork floats above the object instead of sitting on it."),
        ("Twenty slides of one logo", "No narrative, so reviewers lose the point."),
        ("Huge export files", "A 200MB deck never gets opened or shared."),
    ],
    "practice": [
        "Place one logo on a business card, signage and app icon with matching lighting.",
        "Build a six-slide deck with captions explaining each decision.",
        "Export the deck under 5MB a page with embedded fonts and labelled versions.",
    ],
    "quiz": [
        {"q": "Mockups matter because clients:", "options": ["Prefer pretty slides", "Judge work they can imagine in use", "Cannot read PDFs", "Require them"], "answer": 1},
        {"q": "Artwork is placed in a PSD mockup using:", "options": ["The eraser", "A smart object layer", "A mask only", "The background layer"], "answer": 1},
        {"q": "A presentation should be ordered:", "options": ["Randomly", "As a customer meets the brand", "By file size", "Alphabetically"], "answer": 1},
        {"q": "Deck exports should be:", "options": ["Over 100MB", "Consistent page size, fonts embedded, under 5MB a page", "Screenshots", "Unlabelled"], "answer": 1},
    ],
}


TOPICS["Client Briefs"] = {
    "summary": "Working with clients: interrogating the brief, scoping, presenting options and handling revisions.",
    "lessons": [
        ("Turning a vague request into a real brief",
         "Clients describe solutions, not problems: 'make the logo bigger' usually means 'the message is unclear'. Ask what the piece must achieve, who reads it, what success looks like and what must not change. Write the answers back in one page and get them confirmed in writing - that page is your defence later."),
        ("Scope, deliverables and revisions",
         "State exactly what is included: number of concepts, revision rounds, file formats, timeline and what counts as extra. Two concepts, two revision rounds and a fixed delivery list is a professional default. Unwritten scope is why designers end up redrawing a logo nine times for free."),
        ("Presenting, justifying and taking feedback",
         "Present each concept reasoning first - which brief point it answers - then show it applied. Never present a design you do not believe in. Take feedback on the problem rather than the pixels: 'the headline does not stand out' invites a fix, while 'make it blue' is a solution to an undefined problem."),
    ],
    "terms": [
        ("Brief", "The written statement of what the work must achieve and for whom."),
        ("Scope", "Exactly what the fee includes, and what it does not."),
        ("Revision round", "One consolidated pass of client feedback, agreed in advance."),
        ("Scope creep", "Unbilled extra work creeping in one small request at a time."),
    ],
    "mistakes": [
        ("Starting without a written brief", "Every later disagreement becomes your fault."),
        ("Unlimited revisions", "The project never ends and the effective rate collapses."),
        ("Showing a concept you dislike", "Clients pick the option you presented, not the good one."),
        ("Accepting solution-shaped feedback", "You copy orders instead of solving problems."),
    ],
    "practice": [
        "Convert a vague one-line request into a one-page brief with success criteria.",
        "Write a scope sheet: deliverables, two concepts, two revision rounds, timeline, exclusions.",
        "Present three concepts with written justifications, then log one feedback round properly.",
    ],
    "quiz": [
        {"q": "A client saying 'make the logo bigger' usually means:", "options": ["They love big logos", "The message hierarchy is unclear", "The logo is broken", "The file is wrong"], "answer": 1},
        {"q": "A professional default scope includes:", "options": ["Unlimited ideas", "2 concepts and 2 revision rounds", "Free printing", "All future work"], "answer": 1},
        {"q": "Scope creep is best prevented by:", "options": ["Ignoring emails", "A written scope agreed in advance", "Lowering the price", "Working faster"], "answer": 1},
        {"q": "Good feedback collection asks about:", "options": ["Colours only", "The problem the design must solve", "Your favourite font", "Print costs"], "answer": 1},
    ],
}


TOPICS["Pricing"] = {
    "summary": "Pricing and freelancing: costing the work, quoting, invoicing and protecting the business side.",
    "lessons": [
        ("Pricing models and knowing your numbers",
         "Design is priced by project, by hour or by value delivered. Whatever the model, start from real numbers: monthly costs, available billable hours, tax, and the fact that roughly half your working week is admin, learning and chasing. A day rate derived from that floor prevents quoting below survival level."),
        ("Quoting from the scope",
         "Quote from the scope, not a guess: list deliverables, number of concepts, revision rounds and the licence granted, then price each stage. Send a written quote with an expiry date, a deposit requirement and a clear statement of what triggers an extra fee - extra rounds, new applications, urgent turnaround."),
        ("Invoicing, licences and protection",
         "Invoice with the project name, period, payment terms (14 days is normal), bank details and a due date, and take a deposit before starting. Grant usage rights only on final payment, keep the source files until then, and archive the whole project - contracts, briefs, versions - in case of a dispute."),
    ],
    "terms": [
        ("Day rate", "The minimum you must earn per working day to stay solvent."),
        ("Deposit", "Upfront payment that secures the schedule and filters out time-wasters."),
        ("Licence", "The rights granted to use the delivered artwork, and for how long."),
        ("Billable hours", "The hours you can realistically charge for, not all hours worked."),
    ],
    "mistakes": [
        ("Pricing against the cheapest competitor", "Competing on price alone ends in burnout."),
        ("No deposit", "Work starts, the client disappears, and you are unpaid."),
        ("Unlimited licence by default", "You give away rights you could have sold."),
        ("No written quote", "The invoice amount becomes negotiable after delivery."),
    ],
    "practice": [
        "Calculate your day rate from monthly costs, tax and realistic billable hours.",
        "Write a full quote for a poster series with deliverables, rounds, licence and expiry.",
        "Raise a compliant invoice with terms, deposit and a clear due date.",
    ],
    "quiz": [
        {"q": "A day rate should be based on:", "options": ["A competitor's website", "Your real costs, tax and billable hours", "The minimum wage", "A round number"], "answer": 1},
        {"q": "A deposit mainly protects the designer by:", "options": ["Looking professional", "Securing the schedule and filtering out non-serious clients", "Increasing the price", "Avoiding tax"], "answer": 1},
        {"q": "Usage rights should normally transfer:", "options": ["Before work starts", "On final payment", "Never", "Six months later"], "answer": 1},
        {"q": "A quote must include:", "options": ["Only a total figure", "Deliverables, rounds, licence, expiry and exclusions", "Your CV", "A moodboard"], "answer": 1},
    ],
}


# ======================================================================
# ENGINE - lookup, detailed generic chapters, unique quizzes, helpers
# ======================================================================

import re as _re

_MATCH_STOP = {
    "design", "designs", "designing", "basics", "basic", "essentials",
    "essential", "process", "processes", "introduction", "intro", "advanced",
    "fundamentals", "fundamental", "tools", "tool", "skills", "skill",
    "and", "for", "with", "the", "into", "using", "level", "part",
}

_STOP = {
    "the", "and", "for", "with", "your", "you", "our", "into", "from", "that",
    "this", "what", "when", "then", "than", "very", "will", "each", "some",
    "using", "use", "how", "why", "all", "are", "was", "were", "its", "it",
    "class", "work", "project", "week", "month", "practice", "start", "build",
}


def _tokens(text):
    return {t for t in _re.findall(r"[a-z0-9]+", (text or "").lower())
            if t not in _STOP and len(t) > 2}


def lookup(topic_text, extra=""):
    """Best-matching knowledge-base entry for a topic string, or None.

    Token-overlap matching (so small wording differences still match), with the
    filler words every course syllabus uses - "design", "basics", "essentials",
    "process" ... - excluded from the comparison. Without that, "Poster & Flyer
    Design" would match the Logo Design entry just because both contain
    "design", which wrongly reuses another topic's lessons and questions.
    """
    want = {t for t in (_tokens(topic_text) | _tokens(extra))
            if t not in _MATCH_STOP}
    if not want:
        return None
    best, best_score = None, 0.0
    for key, body in TOPICS.items():
        key_tok = {t for t in _tokens(key) if t not in _MATCH_STOP}
        if not key_tok:
            continue
        score = len(want & key_tok) / float(len(key_tok))
        if score > best_score:
            best, best_score = body, score
    return best if best_score >= 0.5 else None


_MONTH_ANGLES = [
    ("foundations and vocabulary", "define, recognise and name",
     "You should finish this topic able to explain it to a classmate without notes."),
    ("applied practice", "apply, compare and refine",
     "You should finish this topic with at least one piece of work that uses it."),
    ("professional delivery", "critique, price and deliver",
     "You should finish this topic able to defend your choices to a client."),
]
def generic_chapters(topic, career_path, month_number, tasks):
    """Detailed fallback chapters for topics without a knowledge-base entry.

    The three month angles differ and each lesson is built from the real
    sub-tasks the TIMETABLE assigns to this topic, so the text always matches
    what the student is actually being taught that week.
    """
    angle, verbs, outcome = _MONTH_ANGLES[(month_number - 1) % 3]
    tasks = [t for t in (tasks or []) if t]
    lessons = []
    for task in tasks[:5]:
        lessons.append((
            task,
            "Week focus: " + task + ". This lesson covers the %s side of %s: you "
            "will %s the skill in a controlled exercise before using it in the "
            "week's deliverable. Work through the steps in order and keep files "
            "named clearly, because the month project builds directly on them."
            % (angle, topic, verbs),
        ))
    while len(lessons) < 3:
        n = len(lessons) + 1
        lessons.append((
            "%s - working session %d" % (topic, n),
            "Guided working session on %s. %s Bring your previous work, correct "
            "one specific weakness, then extend it by one step. %s"
            % (topic, outcome,
               "Ask your tutor to review before you continue."
               if n == 1 else "Record what changed and why."),
        ))
    return {
        "summary": "%s (%s) - taught across this month's classes."
                   % (topic, angle),
        "lessons": lessons,
        "terms": [(topic, "The month's subject; every task below builds on it."),
                  ("Deliverable", "The finished item you submit this month."),
                  ("Critique", "Structured feedback on your work against the brief."),
                  ("Workflow", "The repeatable order of steps you follow to work.")],
        "mistakes": [
            ("Skipping the exercise", "Attempting the project first means the basics fail under pressure."),
            ("No file structure", "Unnamed, unsorted files make revision and portfolio building painful."),
            ("Ignoring feedback", "Repeating a flagged mistake costs marks in the assessment."),
            ("Working without the brief", "Producing something attractive that answers the wrong question."),
        ],
        "practice": ["Redo this week's exercise from scratch in half the time.",
                     "Write three sentences explaining your main decision to a client.",
                     "Find one professional example and note two things it does better than yours."],
        "quiz": [],
    }


def quiz_for(topic, month_number):
    """Quiz questions for a topic.

    Knowledge-base topics ship their own unique set (disjoint across months, so
    the three books never repeat). The generic path derives stable questions
    from the topic name and month, so two books also differ.
    """
    body = lookup(topic)
    if body and body.get("quiz"):
        return [dict(q) for q in body["quiz"]]
    return _generic_quiz(topic, month_number)


def filler_questions(topic, month_number, n=3):
    """Topic- and month-specific questions used to top up an exam so a question
    never repeats inside a book or across that course's three books."""
    return _generic_quiz(topic, month_number)[:max(0, int(n))]


def _generic_quiz(topic, month_number):
    return [
        {"q": "In month %d, the main goal of \"%s\" is to:" % (month_number, topic),
         "options": ["Memorise definitions only",
                     "Apply it to real work and defend your choices",
                     "Skip it and move on", "Copy an existing example"],
         "answer": 1},
        {"q": "Which habit most improves results on \"%s\"?" % topic,
         "options": ["Working without a brief", "Structured practice then critique",
                     "Never asking for feedback", "Changing tools weekly"],
         "answer": 1},
        {"q": "Before submitting work on \"%s\" you should:" % topic,
         "options": ["Check it against the brief", "Add more decoration",
                     "Delete your notes", "Start a different project"],
         "answer": 0},
        {"q": "The fastest way to improve in \"%s\" is:" % topic,
         "options": ["Waiting for a tutor",
                     "Repeat, measure, correct one weakness at a time",
                     "Buying more software", "Copying a finished file"],
         "answer": 1},
        {"q": "Which file habit protects your marks on \"%s\"?" % topic,
         "options": ["Saving one master file only",
                     "Clear names, versions and backups",
                     "Emailing files to yourself", "Printing everything"],
         "answer": 1},
    ]


def week_split(count, weeks=4):
    """Chunk a topic list into weeks using the SAME rule as the timetable
    (per_week = count // 4 + 1), cycling the month's topics when a week would
    otherwise be empty."""
    per_week = max(1, count // weeks + 1) if count else 1
    out = []
    for w in range(weeks):
        chunk = list(range(w * per_week, min((w + 1) * per_week, count)))
        if not chunk and count:
            chunk = [(w + i) % count for i in range(min(per_week, count))]
        out.append(chunk)
    return out