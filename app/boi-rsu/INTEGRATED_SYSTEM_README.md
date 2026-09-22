# INTEGRATED LEARNING SYSTEM v5
## Complete AI-Powered Course Generation Platform

Combines three powerful systems into ONE unified platform:
- **Deep Research Engine** (Apify + GLM-5.2)
- **PDF Generation** (FPDF & ReportLab/FLUX.1-dev)
- **Curriculum Management** (Google Gemini + Deepgram TTS)

---

## 🚀 QUICK START

### 1. Installation

```bash
# Navigate to the project
cd /path/to/backend/app/boi-rsu

# Install dependencies (handled automatically by script)
python integrated_learning_system.py "Your Topic"
```

### 2. Set Environment Variables

Create `.env.local` or `.env` in the backend folder with:

```bash
# NVIDIA - Required for GLM-5.2 course generation
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxx

# Google - Optional (backup AI provider)
GOOGLE_API_KEY=your-google-api-key

# Apify - Required for deep internet research
APIFY_TOKEN=apify_xxxxxxxxxxxxx

# Deepgram - Optional (for text-to-speech)
DEEPGRAM_API_KEY=your-deepgram-key

# Tavily - Optional (for learning resources)
TAVILY_API_KEY=your-tavily-key

# OpenAI - Optional (fallback for voice)
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
```

### 3. Run the System

```bash
# Generate a complete course (simple PDF)
python integrated_learning_system.py "Machine Learning Basics"

# Generate with illustrated PDF (requires NVIDIA_API_KEY)
python integrated_learning_system.py "Web Development" --pdf-style illustrated

# Generate both PDF styles
python integrated_learning_system.py "Python Advanced" --pdf-style both

# Skip text-to-speech
python integrated_learning_system.py "Data Science" --no-voice

# Custom output directory
python integrated_learning_system.py "Topic" --output-dir my_courses

# Custom cache for images
python integrated_learning_system.py "Topic" --cache-dir my_image_cache
```

---

## 🎯 THREE INTEGRATED SYSTEMS

### System 1: Deep Research Engine
**From: ai_learning_system_v4 (14).py**

Performs multi-stage internet research:
1. **Phase 1**: Runs 5 targeted Google searches on different angles
2. **Phase 2**: Apify scrapes full text from 10+ high-quality sources simultaneously
3. **Phase 3**: GLM-5.2 synthesizes everything into ONE comprehensive master document

```
Input: Topic ("Machine Learning Basics")
  ↓
Phase 1: Search [Official Docs, Beginner Guides, Best Practices, Examples, etc.]
  ↓
Phase 2: Scrape [10+ URLs with Apify]
  ↓
Phase 3: GLM-5.2 Synthesizes → Master Notes (8000+ words)
  ↓
Output: Complete, fact-grounded knowledge base
```

**APIs Used:**
- Apify Google Search & Web Scraper
- NVIDIA GLM-5.2 (via OpenAI-compatible API)

---

### System 2: Course Generation
**From: ai_learning_system_v4 (14).py + lesson2.py**

Converts master notes into structured course:
1. **Phase 4**: Generates course outline with 8-15 sections
2. **Phase 5**: Creates detailed content for each section (~500-840 words each)

Each section includes:
- Clear title and learning objectives
- Progressive, layered learning
- Practical examples with Nigerian context
- ~5-7 minute narration time (at 140 wpm)

```
Master Notes
  ↓
Phase 4: Structure Course (8-15 Sections)
  ↓
Phase 5: Generate Section Content (500-840 words each)
  ↓
Output: Complete course structure (ready for PDF/voice)
```

**APIs Used:**
- NVIDIA GLM-5.2 or Google Gemini

---

### System 3: PDF & Voice Output
**From: lesson1.py + lesson2.py**

Two PDF generation styles:

#### Option A: Simple PDF (FPDF2)
```
Course Structure
  ↓
Format with FPDF2
  ↓
Output: Clean, fast PDF
  • No images
  • Small file size
  • Instant generation
```

#### Option B: Illustrated PDF (ReportLab + FLUX.1-dev)
```
Course Structure
  ↓
Generate illustrations for each section (NVIDIA FLUX.1-dev)
  ↓
Format with ReportLab
  ↓
Output: Professional, polished PDF
  • AI-generated illustrations
  • Educational styling
  • Beautiful typography
  • Cached image generation
```

#### Voice Narration (Deepgram Aura-2)
```
Combine all section content
  ↓
Split into 3000-char chunks
  ↓
Deepgram text-to-speech
  ↓
Play audio automatically
  ↓
Perfect for 90-minute class
```

**Libraries Used:**
- `fpdf2` - Simple PDF generation
- `reportlab` - Professional layouts
- `PIL` - Image processing
- Deepgram Aura-2 API - Text-to-speech

---

## 📋 FEATURES COMPARISON

| Feature | System 1 | System 2 | System 3 |
|---------|----------|----------|----------|
| Research | ✅ Apify | - | - |
| Synthesis | ✅ GLM-5.2 | - | - |
| Structure | - | ✅ GLM-5.2 | - |
| Content Gen | - | ✅ GLM-5.2 | - |
| Simple PDF | - | - | ✅ FPDF2 |
| Illustrated PDF | - | - | ✅ ReportLab+FLUX |
| Text-to-Speech | - | - | ✅ Deepgram |
| Interactive Menu | ✅ Yes | - | - |
| Learning Resources | ✅ Yes | - | - |
| Curriculum Templates | - | ✅ Gemini | - |

---

## 🔧 CONFIGURATION

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `NVIDIA_API_KEY` | Yes (for GLM-5.2) | Course generation + illustration |
| `GOOGLE_API_KEY` | Optional | Backup AI provider |
| `APIFY_TOKEN` | Yes (for research) | Internet research & scraping |
| `DEEPGRAM_API_KEY` | Optional | Text-to-speech narration |
| `TAVILY_API_KEY` | Optional | Learning resource discovery |
| `FAST_MODE` | Optional | true/false – uses fewer sources |
| `TARGET_SECTIONS` | Optional | Default: 8 (fast) or 15 (full) |
| `WORDS_PER_SECTION` | Optional | Default: 500 (fast) or 840 (full) |

### Fast Mode vs Full Mode

**Fast Mode** (default):
- 3 research queries instead of 5
- 2 results per query instead of 3
- 8 course sections instead of 15
- 500 words per section instead of 840
- ~10-15 minutes total

**Full Mode**:
- 5 research queries
- 3 results per query
- 15 course sections
- 840 words per section
- ~30-45 minutes total

Enable Full Mode:
```bash
export FAST_MODE=false
python integrated_learning_system.py "Your Topic"
```

---

## 📁 OUTPUT STRUCTURE

```
courses/
├── machine_learning_basics_simple.pdf      # FPDF version
├── machine_learning_basics_illustrated.pdf # ReportLab+FLUX version
└── cache/
    ├── image_hash_1.png  # Cached FLUX illustrations
    ├── image_hash_2.png
    └── ...
```

---

## 🎓 WORKFLOW EXAMPLES

### Example 1: Quick Course Generation
```bash
python integrated_learning_system.py "React Hooks" --pdf-style simple --no-voice
```
**Time: ~5 minutes**
- Research: 2-3 min
- Generation: 2-3 min
- Output: `react_hooks_simple.pdf`

### Example 2: Full Course with Illustrations
```bash
python integrated_learning_system.py "Python Async Programming" --pdf-style illustrated
```
**Time: ~20 minutes**
- Research: 5 min
- Generation: 8 min
- Illustrations: 4 min
- Voice: 3 min
- Outputs: Both PDFs + audio narration

### Example 3: Learning Resources Integration
```bash
python integrated_learning_system.py "TypeScript Advanced"
```
**Includes:**
- Deep internet research
- Curated learning resources
- Complete course
- PDFs + voice

---

## 🐛 TROUBLESHOOTING

### Error: "No AI clients available"
- Check `NVIDIA_API_KEY` or `GOOGLE_API_KEY` in `.env`
- Run: `echo $NVIDIA_API_KEY` to verify

### Error: "Apify scrape error"
- Verify `APIFY_TOKEN` is set
- Check Apify account has credits
- Try a simpler topic

### PDF generation slow
- Use `--pdf-style simple` (skips image generation)
- Set `FAST_MODE=true`
- Increase `--cache-dir` size if reusing

### No voice output
- Ensure `DEEPGRAM_API_KEY` is set
- Use `--no-voice` flag to skip
- Check system audio is enabled

### Images not generating
- Verify `NVIDIA_API_KEY` works
- Check rate limits (free tier: 5 req/min)
- Use `--cache-dir` to reuse previous images

---

## 📊 SYSTEM ARCHITECTURE

```
User Input (Topic)
  ↓
┌─────────────────────────────────┐
│    INTEGRATED LEARNING SYSTEM   │
├─────────────────────────────────┤
│                                 │
│  Phase 1-3: RESEARCH ENGINE     │
│  ├─ Apify Google Search         │
│  ├─ Apify Web Scraper           │
│  └─ GLM-5.2 Synthesize          │
│                                 │
│  Phase 4-5: COURSE GENERATION   │
│  ├─ Structure with GLM-5.2      │
│  └─ Content with GLM-5.2        │
│                                 │
│  Phase 6: PDF OUTPUT            │
│  ├─ FPDF2 (simple)              │
│  ├─ ReportLab+FLUX (illustrated)│
│  └─ Cache images                │
│                                 │
│  Phase 7: VOICE OUTPUT          │
│  └─ Deepgram TTS                │
│                                 │
└─────────────────────────────────┘
  ↓
Output: PDFs + Audio
```

---

## 💡 TIPS & BEST PRACTICES

1. **For Nigerian Context**: System automatically uses Nigerian examples (Jumia, Paystack, Lagos, etc.)

2. **Reuse Illustrations**: Image cache prevents regenerating same images
   ```bash
   # Multiple topics using same cache
   python integrated_learning_system.py "Topic 1" --cache-dir shared_cache
   python integrated_learning_system.py "Topic 2" --cache-dir shared_cache
   ```

3. **Batch Processing**: Generate multiple courses
   ```bash
   for topic in "Python" "JavaScript" "React" "Node.js"; do
     python integrated_learning_system.py "$topic" --pdf-style simple
   done
   ```

4. **Custom Quality Settings**:
   ```bash
   # High-quality illustrated PDFs
   export FAST_MODE=false
   python integrated_learning_system.py "Topic" --pdf-style illustrated
   ```

---

## 📜 API RATE LIMITS

| Service | Free Tier | Paid Tier |
|---------|-----------|-----------|
| NVIDIA GLM-5.2 | 100 req/min | Varies |
| NVIDIA FLUX.1-dev | 10 req/min | 50 req/min |
| Google Gemini | 60 req/min | Varies |
| Deepgram | 600k chars/mo | Custom |
| Apify | 7 days free | $49-400+/mo |

---

## 🔗 INTEGRATIONS

This system seamlessly combines:
- ✅ ai_learning_system_v4 (14).py → Research + Structure
- ✅ lesson1.py → Illustrated PDFs (reportlab+FLUX)
- ✅ lesson2.py → BOI RSU curriculum + FPDF generation

All three work together with **zero conflicts** and **unified API** management.

---

## 📞 SUPPORT

For issues with:
- **Research**: Check Apify token and internet connection
- **AI Generation**: Verify NVIDIA/Google API keys
- **PDFs**: Ensure reportlab/fpdf2/PIL installed
- **Voice**: Check Deepgram account and audio device

---

## 📄 LICENSE

Same as parent project (Miro-Fish)

---

**Created**: 2026-08-15
**Version**: 5.0 (Integrated)
**Status**: Production-Ready
