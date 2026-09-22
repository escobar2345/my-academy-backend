# QUICK REFERENCE & EXAMPLES

## 🚀 30-SECOND STARTUP

```bash
# 1. Navigate to folder
cd backend/app/boi-rsu/

# 2. Create .env file with API keys (required: NVIDIA_API_KEY, APIFY_TOKEN)
echo "NVIDIA_API_KEY=nvapi-xxx" > .env
echo "APIFY_TOKEN=apify-xxx" >> .env

# 3. Run it!
python integrated_learning_system.py "React Advanced Patterns"
```

---

## 📚 PRACTICAL EXAMPLES

### Example 1: Quick Learning Material (2 min)
**Goal**: Rapid study guide for tomorrow's class

```bash
python integrated_learning_system.py "Python Decorators" \
  --pdf-style simple \
  --no-voice
```

**Output**: `python_decorators_simple.pdf` (5-10 MB)
**Time**: ~5 minutes

---

### Example 2: Beautiful Illustrated Course (30 min)
**Goal**: Professional-looking course for students

```bash
python integrated_learning_system.py "Full Stack JavaScript" \
  --pdf-style illustrated \
  --cache-dir ./shared_cache
```

**Output**: 
- `full_stack_javascript_illustrated.pdf` (20-30 MB)
- Images cached in `./shared_cache/`

**Time**: ~20-30 minutes

---

### Example 3: Both Formats + Voice (45 min)
**Goal**: Complete course package (PDF + Audio)

```bash
python integrated_learning_system.py "Advanced Python" \
  --pdf-style both \
  --output-dir ./courses/advanced_python
```

**Output**:
- `advanced_python_simple.pdf`
- `advanced_python_illustrated.pdf`
- Automatic voice narration (MP3)

**Time**: ~40-50 minutes

---

### Example 4: Nigerian Tech Context (15 min)
**Goal**: Course with Nigerian examples

```bash
# System automatically includes:
# - Jumia, Paystack, Flutterwave
# - Lagos, Nigeria-specific examples
# - Local tech industry references

python integrated_learning_system.py "FinTech Apps" \
  --pdf-style simple
```

---

### Example 5: Batch Processing Multiple Topics

```bash
#!/bin/bash

topics=(
  "Python Basics"
  "JavaScript ES6"
  "React Fundamentals"
  "Node.js API Design"
  "SQL Optimization"
)

for topic in "${topics[@]}"; do
  echo "📚 Generating: $topic"
  python integrated_learning_system.py "$topic" \
    --pdf-style simple \
    --cache-dir ./shared_cache
done

echo "✅ All courses generated!"
```

---

### Example 6: Full Mode for Deep Learning

```bash
# Full mode = more research, more content, more depth
export FAST_MODE=false
export TARGET_SECTIONS=15
export WORDS_PER_SECTION=840

python integrated_learning_system.py "Machine Learning Fundamentals"
```

**Result**: 
- 15 detailed sections (not 8)
- 840 words per section (not 500)
- 5 research queries (not 3)
- 3 URLs per query (not 2)
- ~50-60 minutes total

---

## 🎯 USE CASE REFERENCE

| Use Case | Command | PDF Style | Voice | Time |
|----------|---------|-----------|-------|------|
| Quick study guide | `python ... Topic` | simple | no | 5 min |
| Student handout | `... --pdf-style illustrated` | illustrated | yes | 30 min |
| Teacher prep | `... --pdf-style simple --no-voice` | simple | no | 5 min |
| Class material | `... --pdf-style both` | both | yes | 45 min |
| Presentation deck | (export illustrated PDF to PPT) | illustrated | no | 35 min |
| Audio course | `... --no-voice` + post-process | none | custom | varies |

---

## 🔧 COMMON CONFIGURATIONS

### Config 1: Production (Reliability)
```bash
# .env
NVIDIA_API_KEY=nvapi-xxxxx        # Required
APIFY_TOKEN=apify-xxxxx            # Required  
GOOGLE_API_KEY=your-google-key     # Fallback
FAST_MODE=true                      # Speed
```

### Config 2: Development (Features)
```bash
# .env
NVIDIA_API_KEY=nvapi-xxxxx
APIFY_TOKEN=apify-xxxxx
DEEPGRAM_API_KEY=dg_xxxxx          # Voice
TAVILY_API_KEY=tvly_xxxxx          # Resources
FAST_MODE=false                    # Full quality
```

### Config 3: Budget (Minimal API Calls)
```bash
# .env
NVIDIA_API_KEY=nvapi-xxxxx         # GLM-5.2 only
GOOGLE_API_KEY=your-google-key     # Fallback
APIFY_TOKEN=apify-xxxxx
FAST_MODE=true                     # 3 searches max
```

---

## 📊 ESTIMATED COSTS (Monthly)

### Light Usage (10 courses/month)
- NVIDIA API: ~$5-10
- Apify: ~$5-15
- Deepgram: Free tier sufficient
- Total: ~$10-25/month

### Medium Usage (50 courses/month)
- NVIDIA API: ~$25-50
- Apify: ~$25-50
- Deepgram: $49-200
- Google (fallback): ~$0-10
- Total: ~$100-310/month

### High Usage (500+ courses/month)
- NVIDIA API: Custom pricing
- Apify: $49-400/month
- Deepgram: Custom
- Consider enterprise plan

---

## ⚡ PERFORMANCE TIPS

### Tip 1: Reuse Image Cache
```bash
# Multiple courses share the same cache
python integrated_learning_system.py "Topic 1" --cache-dir ./cache
python integrated_learning_system.py "Topic 2" --cache-dir ./cache
python integrated_learning_system.py "Topic 3" --cache-dir ./cache
# Saves 40% generation time
```

### Tip 2: Parallel Generation
```bash
# Run multiple courses simultaneously
(python integrated_learning_system.py "Python" --pdf-style simple &) &
(python integrated_learning_system.py "JavaScript" --pdf-style simple &) &
wait
# Uses API rate limits efficiently
```

### Tip 3: Preview before Full Generation
```bash
# Fast mode first
export FAST_MODE=true
python integrated_learning_system.py "Topic" --pdf-style simple --no-voice

# Then full mode if satisfied
export FAST_MODE=false
python integrated_learning_system.py "Topic" --pdf-style illustrated
```

### Tip 4: Schedule Off-Peak Generation
```bash
# Schedule for 2 AM when APIs are fast
0 2 * * * /home/user/generate_courses.sh
```

---

## 🐛 TROUBLESHOOTING QUICK FIXES

| Error | Fix |
|-------|-----|
| "No AI clients" | Check `NVIDIA_API_KEY` and `GOOGLE_API_KEY` |
| "Apify error" | Verify `APIFY_TOKEN`, check account balance |
| "Image generation failed" | NVIDIA API rate limit – wait 5 min |
| "PDF is huge" | Use `--pdf-style simple` (skip images) |
| "No voice output" | Set `DEEPGRAM_API_KEY` or use `--no-voice` |
| "PDF download slow" | Illustrated PDFs are 20-30 MB, use simple version |

---

## 📈 MONITORING & LOGGING

### Enable Detailed Output
```bash
# Add to .env
DEBUG=true  # Shows all API calls

python integrated_learning_system.py "Topic"
```

### Track Generation Times
```bash
python integrated_learning_system.py "Topic" 2>&1 | tee course_gen.log
```

### Monitor API Usage
```bash
# View Apify dashboard
open https://console.apify.com

# View NVIDIA usage
# In NVIDIA developer portal
```

---

## 🎓 EDUCATIONAL WORKFLOW

### Week 1: Create Course Library
```bash
# Create 10 foundational courses
for week_topic in "HTML" "CSS" "JS Basics" "React" "Node"; do
  python integrated_learning_system.py "$week_topic" --pdf-style simple
done
```

### Week 2-4: Generate Weekly Courses
```bash
# Generate detailed courses for weekly teaching
export FAST_MODE=false
python integrated_learning_system.py "Week 1 Topic" --pdf-style both
python integrated_learning_system.py "Week 2 Topic" --pdf-style both
```

### Ongoing: Maintain Course Library
```bash
# Update courses as new info emerges
python integrated_learning_system.py "Updated Topic" --cache-dir ./cache
```

---

## 🌍 INTERNATIONAL EXAMPLES

### Nigerian Focus
```bash
python integrated_learning_system.py "Digital Marketing in Nigeria"
# Includes: Jumia, Konga, Lagos tech scene, Naira payment systems
```

### Pan-African
```bash
python integrated_learning_system.py "E-Commerce in Africa"
# Includes: Regional examples, payment methods, cultural context
```

### Global
```bash
python integrated_learning_system.py "International Business"
# Includes: World examples, English-language focus
```

---

## 🔒 SECURITY BEST PRACTICES

### Protect API Keys
```bash
# Use environment file (NOT committed to git)
echo ".env" >> .gitignore

# Or use system environment variables
export NVIDIA_API_KEY="nvapi-xxxxx"
export APIFY_TOKEN="apify-xxxxx"
```

### Audit API Usage
```bash
# Log all generations
python integrated_learning_system.py "Topic" > logs/$(date +%Y%m%d).log
```

### Rate Limiting
```bash
# Respect API limits
sleep 60  # 1 minute between requests to stay under rate limits
python integrated_learning_system.py "Topic 1"
sleep 60
python integrated_learning_system.py "Topic 2"
```

---

## 📞 GETTING HELP

### Common Questions

**Q: How do I know if my API keys are correct?**
```bash
# Try generating a simple course
python integrated_learning_system.py "Python" --pdf-style simple --no-voice
# If it works, keys are valid
```

**Q: Can I generate multiple topics in parallel?**
```bash
# Yes, but respect API rate limits
for topic in topic1 topic2 topic3; do
  python integrated_learning_system.py "$topic" --pdf-style simple &
done
wait
```

**Q: How long does a full course take?**
- Simple: 5-10 minutes
- Illustrated: 20-30 minutes
- With voice: +5-10 minutes

**Q: Can I customize the output?**
```bash
# Modify the script itself to customize:
# - Colors and styling
# - Section count
# - Word count per section
# - AI system prompts
```

---

## 📝 REFERENCE SNIPPETS

### Snippet 1: Integration into Flask App
```python
from integrated_learning_system import generate_full_course, generate_simple_pdf

@app.route('/api/generate-course', methods=['POST'])
def generate_course():
    topic = request.json.get('topic')
    client = setup_nvidia_ai()
    course = generate_full_course(client, topic, deep_research(topic, client))
    output_path = generate_simple_pdf(course, f'/tmp/{topic}.pdf')
    return {'pdf_path': output_path}
```

### Snippet 2: Scheduled Generation
```python
import schedule
import time

def job():
    topics = ['AI', 'Web Dev', 'Data Science']
    for topic in topics:
        os.system(f'python integrated_learning_system.py "{topic}"')

schedule.every().day.at("02:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Snippet 3: Quality Assurance
```bash
#!/bin/bash
# Verify all outputs
for pdf in courses/*.pdf; do
  file "$pdf" | grep -q "PDF" && echo "✅ $pdf" || echo "❌ $pdf"
done
```

---

## 🎯 NEXT STEPS

1. **Setup** → Copy environment variables to `.env`
2. **Test** → Run `python integrated_learning_system.py "Test Topic"`
3. **Customize** → Modify prompts and styling in the code
4. **Deploy** → Integrate into your application
5. **Monitor** → Track API usage and generation times
6. **Optimize** → Adjust Fast/Full mode based on needs

---

**Quick Reference Version**: 1.0
**Last Updated**: 2026-08-15
