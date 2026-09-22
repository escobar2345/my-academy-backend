# INTEGRATION MAP: How All Three Systems Work Together

## 📊 System Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   INTEGRATED LEARNING SYSTEM v5                         │
└─────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │    User Input    │
                              │  "Learn Topic X" │
                              └────────┬─────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
        ┌───────────▼──────────┐          ┌──────────────▼─────────┐
        │  ai_learning_system  │          │   lesson1.py           │
        │    v4 (14).py        │          │ (Illustrated PDFs)     │
        ├──────────────────────┤          ├────────────────────────┤
        │ PHASE 1: Research    │          │ ReportLab + FLUX.1-dev │
        │ ├─ Apify Google      │          │ ├─ Image Generation    │
        │ ├─ Scrape 10+ URLs   │          │ ├─ PDF Styling         │
        │ └─ Collect Data      │          │ └─ Cover Pages         │
        │                      │          │                        │
        │ PHASE 2: Synthesis   │          │ INPUT: Course Data     │
        │ ├─ GLM-5.2 Analyze   │          │ OUTPUT: Beautiful PDF  │
        │ └─ Master Notes      │          └────────────────────────┘
        │                      │
        │ PHASE 3: Structure   │          ┌────────────────────────┐
        │ ├─ Create Outline    │          │   lesson2.py           │
        │ ├─ 8-15 Sections     │          │ (Simple FPDF PDFs)     │
        │ └─ Section Titles    │          ├────────────────────────┤
        │                      │          │ FPDF2 + Gemini         │
        │ PHASE 4: Generation  │          │ ├─ Simple PDFs         │
        │ ├─ GLM-5.2 Content   │          │ ├─ BOI Curriculum      │
        │ ├─ 500-840 words     │          │ ├─ Teaching Scripts    │
        │ ├─ Examples + Focus  │          │ └─ Lesson Notes        │
        │ └─ Complete Course   │          │                        │
        │                      │          │ INPUT: Course Structure│
        │ PHASE 5: Voice       │          │ OUTPUT: Quick PDF      │
        │ ├─ Deepgram TTS      │          └────────────────────────┘
        │ ├─ Audio Narration   │
        │ └─ 90-minute class   │
        └───────┬──────────────┘
                │
                ▼
        ┌──────────────────┐
        │   PDF SELECTOR   │
        ├──────────────────┤
        │  --pdf-style     │
        │  ├─ simple       │─────→ FPDF2 Generator
        │  ├─ illustrated  │─────→ ReportLab Generator
        │  └─ both         │─────→ Both generators
        └────────┬─────────┘
                 │
      ┌──────────┴──────────┐
      │                     │
      ▼                     ▼
  ┌─────────┐           ┌──────────┐
  │ PDF Out │           │Audio Out │
  ├─────────┤           ├──────────┤
  │ .pdf    │           │ .mp3     │
  │ Files   │           │ Playback │
  └─────────┘           └──────────┘
```

---

## 🔄 DATA FLOW DIAGRAM

```
STEP 1: RESEARCH (ai_learning_system_v4)
─────────────────────────────────────────
  Topic Input
    │
    ├─→ Search Engine (Apify)
    │   └─→ 5 searches on different angles
    │
    ├─→ Web Scraper (Apify)
    │   └─→ Extract text from 10+ URLs
    │
    └─→ GLM-5.2 Synthesis
        └─→ Master Notes (~8000 words)


STEP 2: STRUCTURING (ai_learning_system_v4)
────────────────────────────────────────────
  Master Notes
    │
    └─→ GLM-5.2 Structure
        └─→ Course Outline
            ├─ 8-15 Sections
            ├─ Learning Objectives
            ├─ Key Concepts
            └─ Duration Estimates


STEP 3: GENERATION (ai_learning_system_v4)
───────────────────────────────────────────
  Course Structure
    │
    └─→ GLM-5.2 Content Generation
        └─→ For each section:
            ├─ 500-840 words content
            ├─ Nigerian examples
            ├─ Practical examples
            └─ Conversational tone


STEP 4: PDF GENERATION (lesson1.py OR lesson2.py)
──────────────────────────────────────────────────
  
  ┌─────────────────────────┬─────────────────────────┐
  │  Path A: Illustrated    │  Path B: Simple         │
  │  (lesson1.py)           │  (lesson2.py)           │
  ├─────────────────────────┼─────────────────────────┤
  │                         │                         │
  │ 1. For each section:    │ 1. Create PDF object    │
  │    Generate image via   │    (FPDF2)              │
  │    NVIDIA FLUX.1-dev    │                         │
  │    (prompt→PNG)         │ 2. Add title page       │
  │                         │                         │
  │ 2. Use ReportLab to     │ 3. For each section:    │
  │    build PDF with:      │    Add formatted text   │
  │    - Cover image        │                         │
  │    - Section images     │ 4. Output PDF           │
  │    - Professional style │                         │
  │                         │                         │
  │ 3. Cache images for     │ 5. Fast generation      │
  │    reuse                │    (~2-3 minutes)       │
  │                         │                         │
  │ 4. Output PDF           │                         │
  │    (~10-15 minutes)     │                         │
  │                         │                         │
  └─────────────────────────┴─────────────────────────┘


STEP 5: VOICE NARRATION (ai_learning_system_v4)
────────────────────────────────────────────────
  All Section Content
    │
    ├─→ Combine into one text
    │
    ├─→ Split into 3000-char chunks
    │   (for Deepgram limits)
    │
    ├─→ Deepgram Aura-2 TTS
    │   └─→ Convert to MP3
    │
    └─→ Play audio automatically
        (Perfect for 90-minute classes)
```

---

## 🧩 COMPONENT MAPPING

### ai_learning_system_v4 (14).py → integrated_learning_system.py

| Function | Location | Purpose |
|----------|----------|---------|
| `install_package()` | Top | Auto-install deps |
| `load_env_file()` | Config | Load env vars |
| `banner()`, `section()`, `ok()`, `err()` | UI | Console output |
| `setup_nvidia_ai()` | AI Setup | Initialize GLM-5.2 |
| `call_nvidia_ai()` | AI Calls | Call GLM-5.2 |
| `speak_text()` | Audio | Deepgram TTS |
| `_scrape_urls_apify()` | Research | Web scraping |
| `_search_and_get_urls()` | Research | Google search |
| `deep_research()` | Research | Full research pipeline |
| `generate_course_sections()` | Course Gen | Create outline |
| `generate_section_content()` | Course Gen | Create content |
| `generate_full_course()` | Course Gen | Orchestrate all |

### lesson1.py → integrated_learning_system.py

| Class/Function | Location | Purpose |
|---|---|---|
| `FluxClient` | Image Gen | NVIDIA FLUX.1-dev wrapper |
| `FluxClient.generate()` | Image Gen | Generate illustrations |
| `build_styles()` | PDF Gen | ReportLab styles |
| `build_pdf()` | PDF Gen | Create illustrated PDF |
| `generate_illustrated_pdf()` | PDF Gen | Main illustrated PDF gen |

### lesson2.py → integrated_learning_system.py

| Class/Function | Location | Purpose |
|---|---|---|
| `SimpleCoursePDF` | FPDF | FPDF2-based PDF class |
| `generate_simple_pdf()` | FPDF | Generate simple PDF |

---

## 🔌 API INTEGRATION POINTS

### NVIDIA APIs

```python
# GLM-5.2 (Course Generation)
setup_nvidia_ai()
  └─→ OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_KEY)
      └─→ Used in:
          ├─ deep_research()           # Synthesize research
          ├─ generate_course_sections()  # Create outline
          └─ generate_section_content()  # Generate content

# FLUX.1-dev (Image Generation)
FluxClient(api_key=NVIDIA_KEY)
  └─→ requests.post(NVIDIA_API_URL)
      └─→ Used in:
          └─ generate_illustrated_pdf()  # Create images
```

### Google APIs

```python
# Gemini (Fallback Generation)
setup_google_ai()
  └─→ genai.GenerativeModel("gemini-2.5-flash")
      └─→ Used as fallback if NVIDIA not available
```

### Apify APIs

```python
# Web Research
ApifyClient(token=APIFY_TOKEN)
  ├─→ apify/google-search-scraper
  │   └─→ Used in _search_and_get_urls()
  │
  └─→ apify/web-scraper
      └─→ Used in _scrape_urls_apify()
```

### Deepgram API

```python
# Text-to-Speech
requests.post("https://api.deepgram.com/v1/speak")
  └─→ Used in speak_text()
      └─→ Convert section content to MP3
      └─→ Play automatically
```

---

## 🎛️ COMMAND-LINE OPTIONS

```bash
# Basic usage
python integrated_learning_system.py "Topic"

# PDF Style Selection
--pdf-style simple        # FPDF2 only (fast)
--pdf-style illustrated   # ReportLab+FLUX (beautiful)
--pdf-style both          # Both versions

# Voice Control
--no-voice               # Skip text-to-speech

# Output Control
--output-dir my_courses   # Custom output folder
--cache-dir my_cache      # Custom image cache

# Full list
python integrated_learning_system.py --help
```

---

## ⚙️ CONFIGURATION VARIABLES

### Required APIs

```bash
# For GLM-5.2 course generation
export NVIDIA_API_KEY="nvapi-xxxxxxxxxxxxx"

# For internet research
export APIFY_TOKEN="apify_xxxxxxxxxxxxx"
```

### Optional APIs

```bash
# For Google Gemini fallback
export GOOGLE_API_KEY="your-google-key"

# For Deepgram text-to-speech
export DEEPGRAM_API_KEY="your-deepgram-key"

# For learning resources
export TAVILY_API_KEY="your-tavily-key"
```

### Performance Tuning

```bash
# Fast mode (default)
export FAST_MODE="true"
  # 3 searches, 2 results each, 8 sections, 500 words

# Full mode
export FAST_MODE="false"
  # 5 searches, 3 results each, 15 sections, 840 words

# Custom section count
export TARGET_SECTIONS="10"

# Custom section length
export WORDS_PER_SECTION="600"
```

---

## 📈 WORKFLOW EXECUTION TIMES

### Fast Mode (Default)
```
Research Phase:        2-3 min  ├─ 3 searches
                                └─ 2 URLs per search
                                
Synthesis:             2-3 min  └─ GLM-5.2 master notes

Course Structure:      2-3 min  ├─ Create outline
                                └─ 8 sections

Content Generation:    3-5 min  ├─ 500 words per section
                                └─ GLM-5.2 writing

PDF Generation:        1-2 min  └─ FPDF2 (no images)

Voice Narration:       2-3 min  └─ Deepgram TTS

TOTAL:               ~13-19 min
```

### Full Mode
```
Research Phase:        5-7 min  ├─ 5 searches
                                └─ 3 URLs per search
                                
Synthesis:             5-7 min  └─ GLM-5.2 master notes

Course Structure:      3-5 min  ├─ Create outline
                                └─ 15 sections

Content Generation:    8-12 min ├─ 840 words per section
                                └─ GLM-5.2 writing

Simple PDF:            2-3 min  └─ FPDF2 (no images)

Illustrated PDF:       8-12 min ├─ Generate 15 images
                                └─ ReportLab formatting

Voice Narration:       5-8 min  └─ Deepgram TTS

TOTAL:               ~40-55 min (simple)
TOTAL:               ~50-70 min (illustrated)
```

---

## 🔀 FALLBACK LOGIC

### AI Provider Priority
```
1. NVIDIA GLM-5.2     (Primary)
   └─ If unavailable ↓

2. Google Gemini      (Fallback)
   └─ If unavailable ↓

3. Error             (Abort with message)
```

### PDF Generation Priority
```
1. Simple PDF (FPDF2) ✅ Always available
   └─ Requires nothing extra

2. Illustrated PDF    ⚠️  Requires NVIDIA_API_KEY
   └─ If unavailable → falls back to Simple PDF
```

### Voice Priority
```
1. Deepgram Aura-2    (Preferred)
   └─ If unavailable or --no-voice ↓

2. Skip voice         (Silent mode)
```

---

## 🧪 TESTING THE INTEGRATION

### Test 1: Verify All APIs

```bash
# Check which APIs are available
python integrated_learning_system.py "Test Topic" --pdf-style simple --no-voice
```

Expected output:
```
✅ NVIDIA API connected
✅ Master notes synthesized
✅ Course structured
✅ Content generated
✅ PDF created (simple)
```

### Test 2: Test Illustration Generation

```bash
# Requires NVIDIA_API_KEY
python integrated_learning_system.py "Test Topic" --pdf-style illustrated
```

Expected output:
```
✅ Generating images for 8 sections...
✅ Illustrated PDF created
```

### Test 3: Test Voice

```bash
# Requires DEEPGRAM_API_KEY
python integrated_learning_system.py "Test Topic" --pdf-style simple
```

Expected output:
```
✅ Converting to speech...
✅ Playing audio...
```

---

## 📝 KEY INTEGRATION BENEFITS

| Benefit | How It Works |
|---------|-------------|
| **Single Entry Point** | `integrated_learning_system.py` replaces need to run 3 separate scripts |
| **Unified Configuration** | All APIs configured in one `.env` file |
| **Flexible Output** | Choose PDF style (simple/illustrated/both) and voice (on/off) |
| **Reusable Components** | Image cache shared across multiple course generations |
| **Error Resilience** | Fallback AI providers, skippable steps |
| **Performance Tuning** | Fast/Full modes for different use cases |
| **Nigerian Context** | All content includes local examples automatically |

---

## 🎯 MIGRATION FROM OLD SYSTEM

### Before (3 separate scripts)
```bash
# Step 1: Generate course
python ai_learning_system_v4.py

# Step 2: Create PDF
python lesson1.py OR lesson2.py

# Step 3: Convert to voice
python ai_learning_system_v4.py  # again
```

### After (1 unified script)
```bash
# All in one!
python integrated_learning_system.py "Topic"
```

---

## 📊 COMPARISON: Old vs New

| Aspect | Old System | New System |
|--------|-----------|-----------|
| Scripts to manage | 3 | 1 |
| Configuration files | 3 `.env` files | 1 `.env` file |
| Data handoff | Manual | Automatic |
| Output formats | PDF OR Voice | PDF + Voice |
| API fallbacks | None | Google Gemini |
| Feature discovery | Read 3 codebases | Read 1 README |
| Maintenance | 3× effort | 1× effort |

---

## 🚀 NEXT STEPS

1. ✅ Set up environment variables (see INTEGRATED_SYSTEM_README.md)
2. ✅ Test with: `python integrated_learning_system.py "Python Basics"`
3. ✅ Choose PDF style based on use case
4. ✅ Optimize with Fast/Full mode
5. ✅ Deploy to backend API

---

**Document Version**: 1.0
**Last Updated**: 2026-08-15
**Integration Status**: ✅ Complete
